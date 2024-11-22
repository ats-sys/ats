import os
import sys
import math
import yaml
import time
import glob
import shutil
import datetime
import threading
import pandas as pd
from pathlib import Path
from pprint import pprint
from ciso8601 import parse_datetime

from binance_dataset_collector import DatasetCollector

CACHE_DIR = None  # Set from params


def get_param_from_cmd():
    num_args = len(sys.argv)
    if num_args != 2:
        print('Usage:')
        print('python -m run_dataset_collector_threaded params_file.yaml')
        sys.exit(1)

    params_filename = sys.argv[1]
    return params_filename


def load_params(params_filename):
    file = open(params_filename, "r")
    all_params = yaml.load(file, Loader=yaml.FullLoader)
    return all_params


# Saves parallelly downloaded chunks into a cache folder
def save_to_cache(trades_df, candles_df, start_time, end_time, candle_length_secs):
    start_time_print = start_time.split('.')[0].replace(':', '-')
    end_time_print = end_time.split('.')[0].replace(':', '-')

    filepath = f'{CACHE_DIR}/candles_{candle_length_secs}s_from_{start_time_print}_to_{end_time_print}.csv'

    candles_df.to_csv(filepath, index=False)

    return filepath


# Delete the cache directory if there is one and make a (new) cache directory
def rest_cache():
    try:
        shutil.rmtree(CACHE_DIR)
    except:
        pass
    Path(CACHE_DIR).mkdir(parents=True)


# Merge the chunks in the cache
def merge_cache(start_date, end_date, market, candle_length_secs, save_dir):
    print('\n===== Merging cache ======\n')
    all_file_names = glob.glob(CACHE_DIR + '/*')
    all_file_names.sort()
    all_data = pd.DataFrame([], columns=['time', 'open', 'high', 'low', 'close', 'volume'])

    for i, file_name in enumerate(all_file_names):

        try:
            data = pd.read_csv(file_name)
        except:
            continue

        if i == 0:
            all_data = data
            continue
        last_row = all_data.iloc[-1]

        merge_start_at = 0

        for j, j_row in enumerate(data.iloc):
            if j_row['time'] == last_row['time']:
                merge_start_at = j + 1
                break
        to_be_merged = data.iloc[merge_start_at:-1]
        all_data = pd.concat([all_data, to_be_merged])

    market_name = market.replace("/", "-")

    file_path = f'{save_dir}/candles_{market_name}_{candle_length_secs}s_from_{start_date}_to_{end_date}.csv'
    file_path = file_path.replace(':', '-')  # Windows file names cannot have a colon

    all_data.to_csv(file_path, index=False)
    load_dataset_and_fix_zero_volume_candles(file_path, market)


def load_dataset_and_fix_zero_volume_candles(filename, market):
    df = pd.read_csv(filename)
    collector = DatasetCollector(market=market)
    df = collector._fix_zero_volume_candles(df)

    df.to_csv(filename, index=False)

    print(f'Complete dataset saved to: {filename}')


# Run the data collection in a threaded manner
def collect_dataset_threaded(market, start_ts, end_ts, params):
    TIME_FOR_ONE_THREAD = 1  # In hours

    candle_length_secs = params['candle_length_secs']
    thread_pool_size = params['thread_pool_size']
    save_dir = params['save_dir']

    rest_cache()  # Reset the data cache

    start_ts_obj = parse_datetime(start_ts)
    end_ts_obj = parse_datetime(end_ts)
    delta_dates = end_ts_obj - start_ts_obj
    delta_t = math.ceil(delta_dates.total_seconds() / 60 / 60 / TIME_FOR_ONE_THREAD)

    sequence_size = math.ceil(delta_t / thread_pool_size)

    step_t = 0

    print(f'delta_t: {delta_t}, sequence_size: {sequence_size}')

    for step in range(sequence_size):
        threads = []
        for i in range(thread_pool_size):

            if step_t >= delta_t:
                break

            step_start_date_obj = start_ts_obj + datetime.timedelta(hours=step_t * TIME_FOR_ONE_THREAD)
            step_end_date_obj = start_ts_obj + datetime.timedelta(hours=(step_t + 1) * TIME_FOR_ONE_THREAD)

            step_end_date_obj = step_end_date_obj + datetime.timedelta(
                seconds=120)  # Add 2 more minutes to make sure all the candles are captured. TODO why ?

            start_time = f'{step_start_date_obj.strftime("%Y-%m-%dT%H:%M:%S")}+00:00'
            end_time = f'{step_end_date_obj.strftime("%Y-%m-%dT%H:%M:%S")}+00:00'

            i_thread = threading.Thread(target=collect_dataset_chunk,
                                        args=(start_time, end_time, market, candle_length_secs,))
            i_thread.start()
            threads.append(i_thread)

            step_t += 1

        for i_thread in threads:
            i_thread.join()

    merge_cache(start_ts, end_ts, market, candle_length_secs, save_dir)


# Collect data from ftx and convert into candles
def collect_dataset_chunk(start_time, end_time, market, candle_length_secs):
    collector = DatasetCollector(market=market)

    # ---------------------
    # Data collection
    trades_df = collector.get_trades_df(start_time, end_time)

    # ---------------------
    # Candles conversion
    candles_df = collector.convert_to_candles(trades_df, candle_length_secs, separate_volumes=True)
    file_path = save_to_cache(trades_df, candles_df, start_time, end_time, candle_length_secs)
    # print(f'Downloaded chunk saved to: {file_path}')


def create_dir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)


def ts_to_datetime(ts, d_format='%Y-%m-%dT%H:%M:%S.0'):
    return datetime.datetime.utcfromtimestamp(ts).strftime(d_format)


def main():
    params_filename = get_param_from_cmd()
    params = load_params(params_filename)

    global CACHE_DIR
    CACHE_DIR = os.path.join(params['save_dir'], 'cache')

    create_dir(params['save_dir'])
    create_dir(CACHE_DIR)

    print('Running threaded dataset collector with following parameters.')
    pprint(params)

    if params["use_timestamps"]:
        assert (isinstance(params['from_list'][0], float) or isinstance(params['from_list'][0], int)), "make use_timestamps: False in parameter file if you are not using timestamps to download the data"
        start_ts_list = [ts_to_datetime(f_ts) for f_ts in params['from_list']]
        end_ts_list = [ts_to_datetime(t_ts) for t_ts in params['to_list']]
    else:
        start_ts_list = params['from_list']
        end_ts_list = params['to_list']

    for market in params['markets']:
        for start_ts, end_ts in zip(start_ts_list, end_ts_list):
            start_time = datetime.datetime.now()

            collect_dataset_threaded(market, start_ts, end_ts, params)

            end_time = datetime.datetime.now()
            print(f'Total download time: {(end_time - start_time)}')
            print(
                f'---------------------------{market} Part {start_ts} - {end_ts} Completed--------------------------------------')
        print(f'---------------------------{market} Download Completed--------------------------------------')


if __name__ == '__main__':
    if os.environ.get('BINANCE_API_KEY') is None or os.environ.get('BINANCE_API_SECRET') is None:
        raise Exception("Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")

    main()
