import os
import time
import traceback
import numpy as np
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from ciso8601 import parse_datetime
from typing import Optional, Dict, Any, List

from binance.spot import Spot


class DatasetCollector:
    def __init__(self, market) -> None:
        http_client_params = {
            'api_key': os.environ.get('BINANCE_API_KEY'),
            'api_secret': os.environ.get('BINANCE_API_SECRET'),
            'base_url': 'https://api.binance.com',
            'timeout': 60
        }

        self.client = Spot(**http_client_params)

        self.market = market
        self.REQ_LIMIT_PER_MIN = 1200  # binance request rate limit

    def get_trades_df(self, start_time, end_time, drop_extra_cols=True):
        start_ts = parse_datetime(start_time).timestamp()
        end_ts = parse_datetime(end_time).timestamp()

        if end_ts <= start_ts:
            print('>>>>>>>>>>>>>> >>>>>>>>>>> >>>>>>>>> Time error: ', end_ts - start_ts)

        assert end_ts > start_ts  # Incorrect time specification
        duration = end_ts - start_ts

        print(f'Market: {self.market}. Collecting data from {start_time} to {end_time}. '
              f'Duration: {int(duration)} secs = {duration / 60: .1f} mins = '
              f'{duration / 3600: .1f} hrs = {duration / (3600 * 24)} days')

        trades = self._get_all_trades(start_ts, end_ts)
        trades_df = pd.DataFrame(trades)

        return trades_df

    def convert_to_candles(self, trades_df, candle_length_secs, separate_volumes=False, fix_zero_vol_candles=False):
        # The agg operation gives a MultiIndex for columns (for aggregated columns)
        # Also, The 'time' column is removed and it is made the index of candles_df

        resample_rule = f'{candle_length_secs}S'
        trades_df.reset_index(level=0, inplace=True)

        if trades_df is None or trades_df.empty:
            return pd.DataFrame([])

        agg_rule = {
            'p': ['first', 'max', 'min', 'last'],  # In ohlc order
            'q': 'sum'
        }

        if separate_volumes:
            # Note: 'side' of a trade in this df is the side of limit order (passive side)
            # Since we want to refer to the side of the market order (active side), we flip the flag side here
            trades_df['buy_flag'] = np.where(trades_df['m'] == True, 1, 0)
            trades_df['sell_flag'] = np.where(trades_df['m'] == False, 1, 0)
            trades_df['buy_size'] = trades_df['q'] * trades_df['buy_flag']
            trades_df['sell_size'] = trades_df['q'] * trades_df['sell_flag']

            agg_rule['buy_size'] = 'sum'
            agg_rule['sell_size'] = 'sum'

        candles_df = trades_df.resample(resample_rule, on='T').agg(agg_rule)

        # Flatten the MultiIndex columns and rename them
        candles_df.columns = candles_df.columns.to_flat_index()

        name_mappings = {('p', 'first'): 'open',
                         ('p', 'max'): 'high',
                         ('p', 'min'): 'low',
                         ('p', 'last'): 'close',
                         ('q', 'sum'): 'volume',
                         ('buy_size', 'sum'): 'buy_volume',
                         ('sell_size', 'sum'): 'sell_volume',
                         }

        new_columns = [name_mappings[col] for col in candles_df.columns]
        candles_df.columns = new_columns

        # Make the index (time) a column. This will introduce a new index of integers (o to n)
        candles_df.reset_index(level=0, inplace=True)
        candles_df.rename({'T': 'time'}, axis=1, inplace=True)
        candles_df['time'] = candles_df['time'].apply(lambda x: str(x) + "+00:00")

        if fix_zero_vol_candles:
            candles_df = self._fix_zero_volume_candles(candles_df)

        return candles_df

    def _fix_zero_volume_candles(self, df):
        """ Some candles have zero volume. Set their ohlic prices to the value of the previous row"""

        # open, high, low, close are NaN in zero volume candles

        # If the first row (and more consecutive rows) are zero vol candles, we delete them,
        # because there are no previous candles to replicate

        rows_to_drop = []
        for i in range(len(df)):
            if np.isnan(df['close'].loc[i]):
                rows_to_drop.append(i)
            else:  # First non-zero candle
                break

        if len(rows_to_drop) > 0:
            df.drop(df.index[rows_to_drop], inplace=True)
            df.reset_index(level=0, inplace=True)

        # Set ohlic prices of zero vol candles to the value of the previous rows

        num_zero_vol_candles = 1

        while num_zero_vol_candles > 0:
            idx = np.argwhere(np.isnan(df['close'].values))
            idx = idx.reshape((len(idx),))  # Need only 1 dimension for indexing in df.iloc

            num_zero_vol_candles = len(idx)

            prev_idx = idx - 1

            df.iloc[idx, df.columns == 'open'] = df.iloc[prev_idx, df.columns == 'close']
            df.iloc[idx, df.columns == 'high'] = df.iloc[prev_idx, df.columns == 'close']
            df.iloc[idx, df.columns == 'low'] = df.iloc[prev_idx, df.columns == 'close']
            df.iloc[idx, df.columns == 'close'] = df.iloc[prev_idx, df.columns == 'close']

        return df

    def _get_all_trades(self, start_time, end_time):
        """ This function is taken and adapted from: https://github.com/ftexchange/ftx/blob/master/rest/client.py"""

        # For progress bar
        period_secs = round(end_time - start_time)
        last_start_time = start_time

        all_ids = set()
        limit = 1000
        limit = min(limit, 1000)  # the max limit is 1000 for binance agg_trades API
        results = []
        num_requests = 0
        finished_period = 0

        with tqdm(total=period_secs, disable=False) as pbar:
            pbar.update(finished_period)
            while True:
                try:
                    response = self.__get_trades_history(self.market, start_time, end_time, limit)

                except Exception as e:
                    num_requests += 1

                    if num_requests > 3:
                        break

                    print(f'\nError occurred during trade history retrieval. Sleeping {num_requests*5} secs and retrying'
                          f'\n-error_message: {traceback.print_exc()}')

                    time.sleep(num_requests*5)

                    continue  # We can safely skip the rest of the loop. Next iter will send the same request

                deduped_trades = [
                    r for r in response if r['a'] not in all_ids]

                curr_ids = set()
                timestamps = []
                for trade in deduped_trades:
                    curr_ids.add(trade['a'])
                    dt = parse_datetime(datetime.utcfromtimestamp(trade['T'] / 1000).isoformat())
                    timestamps.append(trade['T'] / 1000)
                    trade['T'] = dt

                results.extend(deduped_trades)

                all_ids |= curr_ids  # Union

                if len(timestamps) == 0:  # Rare case where deduped_trades is empty when response is not
                    timestamps = [trade['T'] / 1000 for trade in response]

                if len(response) == 0 or len(response) < limit:

                    if timestamps:
                        pbar.update(round(end_time - min(timestamps)))

                    break

                res_end_time = max(timestamps)
                res_start_time = min(timestamps)
                start_time = max(timestamps)

                if last_start_time == last_start_time:
                    start_time += 1

                last_start_time = start_time

                finished_period = round(res_end_time - res_start_time)
                pbar.update(finished_period)
                time.sleep(0.2)

        return results

    def __get_trades_history(self, market_name, start_time, end_time, limit=1000) -> List[Dict]:
        # done
        start_time = np.longlong(start_time * 1000)
        end_time = np.longlong(end_time * 1000)

        max_retries = 3
        retry_count = 1

        while retry_count <= max_retries:
            try:
                results = self.client.agg_trades(symbol=market_name, startTime=start_time, endTime=end_time, limit=limit)

                # [
                #     {
                #         "a": 26129, // Aggregate tradeId
                #         "p": "0.01633102", // Price
                #         "q": "4.70443515", // Quantity
                #         "f": 27781, // First                 tradeId
                #         "l": 27781, // Last                 tradeId
                #         "T": 1498793709153, // Timestamp
                #         "m": true, // Was the buyer the maker?
                #         "M": true // Was the trade the best price match?
                #     }
                # ]

                for res in results:
                    res["p"] = float(res["p"])
                    res["q"] = float(res["q"])

                return results

            except Exception as e:
                print(
                    'Error occurred in get_trades_history.'
                    f'\n-error_message: {e}')

                sleep_time = 1 * retry_count  # Sleep longer as we keep retrying
                time.sleep(sleep_time)
                retry_count += 1

                # All retries failed
                if retry_count > max_retries:
                    print('All retries failed. Exiting...')
                    exit(1)
                    assert False, 'All retries failed.'

        return []
