import numpy as np

from ats.utils.logging.logger import logger
from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.order import Order
from ats.exchanges.data_classes.candle import Candle
from ats.strategies.base_strategy import BaseStrategy
from ats.state.order_state_list_state import OrderStateListState
from ats.utils.trading.pending_order_manager import PendingOrderManager
from ats.utils.metrics.metric_utils import find_percentiles, find_sharp_ratio


class BColors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class AdvancedBaseStrategy(BaseStrategy):
    def __init__(self, config, state: SimpleState = None):
        super().__init__(config, state)

        # POM
        self.use_pom = self.config.get("use_pom", False)
        self.price_gap_perc_cancel = self.config.get("price_gap_perc_cancel", 5)
        self.price_gap_perc_reenter = self.config.get("price_gap_perc_reenter", 0.05)
        self.almost_market_order_perc = self.config.get("almost_market_order_perc", 0.01)
        self.pending_order_manager = None

        self.max_residual_orders = 0

        self.liquidating_percentage = self.config.get("liquidating_percentage", 50) / 100
        self.liquidation_asset_ratio = self.config.get("liquidation_asset_ratio", 20)
        self.enable_auto_liquidation = self.config.get("enable_auto_liquidation", False)
        # self.enable_auto_liquidation = False

        self.base_symbol, self.quote_symbol = self.config['base_symbol'], self.config['quote_symbol']

        if self.quote_symbol == "BTC":
            self.min_notional = 0.0001  # ETH/BTC
        else:
            self.min_notional = 5  # BTC/USDT float(self.exchange._Exchange__binance_notional_filter['minNotional'])

        self.order_states = OrderStateListState()

        self.buy_orders = {}
        self.sell_orders = {}
        self.open_trades = {}
        self.liquidation_orders = {}
        self.rejected_order_ids = {}
        self.open_one_sided_orders = {}
        self.single_order_completed_trades = {}

        self.total_pnl = 0
        self.pnl_list = []
        self.pnl_percent_list = []

        self.residual_buy_orders = {}
        self.residual_sell_orders = {}

        self.init_asset_ratio = None
        self.last_trade_time = None

        self.bid = None
        self.ask = None
        self.close = None
        self.base_asset_balance, self.quote_asset_balance = None, None
        self.pending_base_asset_amount, self.pending_quote_asset_amount = None, None

        self.start_time = None
        self.curr_time = None

        self.order_fee_tracker = {"base": 0, "quote": 0}
        self.mm_gain_sub_component_tracker = {"base": 0, "quote": 0}

        self.log_trade_activity = False
        self.verbose = False
        self.verbose_completes = True

        self.order_stats = {
            "buy_sell": 0,
            "buy_only": 0,
            "sell_only": 0,
            "liq_buy": 0,
            "liq_sell": 0
        }

        self.equity_stats = {
            "init_price": None,
            "init_base": None,
            "init_quote": None,
            "init_holding_base": None,
            "init_holding_quote": None,
            "last_price": None,
            "last_base": None,
            "last_quote": None,
            "last_holding_base": None,
            "last_holding_quote": None
        }

        self.pnl_stats = {
            "profitable": 0,
            "loosing": 0,
            "neutral": 0
        }

        self.order_exec_times = {
            "BUY": [],
            "SELL": [],
            "BUY_SELL": []
        }

    def validate_config(self) -> None:
        raise NotImplementedError

    def check_and_place_orders(self, *args, **kwargs):
        """strategy related order placements"""
        raise NotImplementedError

    def update_indicators(self, candle: Candle) -> any:
        """indicator updates should be done here"""
        raise NotImplementedError

    def on_candle(self, candle: Candle) -> None:
        """
        override this method which defines what to do at each new candle
        """
        self.base_asset_balance, self.quote_asset_balance = self._get_balances()
        self.pending_base_asset_amount, self.pending_quote_asset_amount = self._pending_wallet_balances()
        self.close = candle.close
        self.curr_time = candle.time
        self.bid = self.close
        self.ask = self.close

        if self.start_time is None:
            self.start_time = self.curr_time
            self.last_trade_time = candle.time.timestamp()
            self.init_asset_ratio = self.base_asset_balance * candle.close / (self.quote_asset_balance + 1e-6)

            if self.use_pom:
                self.init_pom()

            self.init_plots()

            self.equity_stats["init_price"] = self.close
            self.equity_stats["init_base"] = self.base_asset_balance
            self.equity_stats["init_quote"] = self.quote_asset_balance
            self.equity_stats["init_holding_base"] = self.pending_base_asset_amount
            self.equity_stats["init_holding_quote"] = self.pending_quote_asset_amount

        self.equity_stats["last_price"] = self.close
        self.equity_stats["last_base"] = self.base_asset_balance
        self.equity_stats["last_quote"] = self.quote_asset_balance
        self.equity_stats["last_holding_base"] = self.pending_base_asset_amount
        self.equity_stats["last_holding_quote"] = self.pending_quote_asset_amount

        if self.use_pom:
            self.pending_order_manager.watch_price(candle)

        # self.last_close_prices.append(self.clode)
        self.update_indicators(candle)

        usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity = self._get_equity_balance()
        self.register_plot_data(self.curr_time, usable_base_asset, usable_quote_asset, total_base_asset,
                                total_quote_asset, usable_equity, total_equity)

        # asset liquidation
        asset_ratio, drift = self._check_asset_imbalance_ratio(self.close, self.close, self.base_asset_balance,
                                                               self.quote_asset_balance)
        n_liq_orders = len(self.liquidation_orders)

        if n_liq_orders < 1 and self.enable_auto_liquidation and asset_ratio > self.liquidation_asset_ratio:  # 50: #20: #10:
            self._liquidate_assets(self.base_asset_balance, self.quote_asset_balance, "SELL",
                                   self.liquidating_percentage, self.curr_time)

        elif n_liq_orders < 1 and self.enable_auto_liquidation and asset_ratio < (
                1 / self.liquidation_asset_ratio):  # 0.02: #0.05: #0.1:
            self._liquidate_assets(self.base_asset_balance, self.quote_asset_balance, "BUY",
                                   self.liquidating_percentage, self.curr_time)

        else:
            num_open_trades = len(self.open_trades)
            self.check_and_place_orders()

            # To indicate that the program is running, print dots while waiting for buy condition
            if num_open_trades == 0:
                print(". ", end="", flush=True)

        self.order_states.update()
        self.check_execution(candle)
        self.plot_profit_components(self.curr_time)

    def on_stop(self) -> None:
        """
        This will be called by the trading job when the strategy is stopped
        Returns:
            None
        """
        if self.use_pom:
            # Stopping the pending order manger
            self.pending_order_manager.stop()

        self._get_metric_report()

    def on_new_order_callback(self, new_order, event_candle):
        # orders_n_candles.append([new_order, event_candle, self.__counter])

        if event_candle is not None:  # None candles are received when pending order manger loads previously saved status
            self.open_one_sided_orders[new_order.order_id] = new_order
            self.order_states.add(new_order)

    def on_cancel_order_callback(self, cancelled_order, event_candle):
        pass

    def init_pom(self):
        self.pending_order_manager = PendingOrderManager(exchange=self.exchange,
                                                         config={
                                                             'price_gap_perc_cancel': self.price_gap_perc_cancel,
                                                             'price_gap_perc_reenter': self.price_gap_perc_reenter,
                                                             'almost_market_order_perc': self.almost_market_order_perc},
                                                         id='ans_with_ma_and_pom' + ('_back_trading' if self.exchange.is_back_trading() else '')
                                                         )

        self.pending_order_manager.on_new_order(self.on_new_order_callback)
        self.pending_order_manager.on_cancel_order(self.on_cancel_order_callback)

        self.pending_order_manager.load()  # Reload the previous states from the disk

    def init_plots(self):
        self.exchange.get_plot_data().set_topic(topic='Usable Base Asset Balance ($)', color='blue',
                                                lines_or_markers='lines', pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Usable Quote Asset Balance ($)', color='red',
                                                lines_or_markers='lines', pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Total Base Asset Balance ($)', color='cyan',
                                                lines_or_markers='lines', pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Total Quote Asset Balance ($)', color='orange',
                                                lines_or_markers='lines', pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Usable Equity ($)', color='green', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Total Equity ($)', color='magenta', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Pending Buy Level', color='purple', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Pending Sell Level', color='magenta', lines_or_markers='lines',
                                                pattern='solid')

        self.exchange.get_plot_data().set_topic(topic='Holding Component', color='orange', lines_or_markers='lines',
                                                pattern='solid')

        self.exchange.get_plot_data().set_topic(topic='Half Buy Pending Component', color='blue',
                                                lines_or_markers='lines', pattern='dashdot')
        self.exchange.get_plot_data().set_topic(topic='Half Sell Pending Component', color='blue',
                                                lines_or_markers='lines', pattern='dot')
        self.exchange.get_plot_data().set_topic(topic='Pending Component', color='blue', lines_or_markers='lines',
                                                pattern='solid')

        self.exchange.get_plot_data().set_topic(topic='Fee Component', color='red', lines_or_markers='lines',
                                                pattern='solid')

        self.exchange.get_plot_data().set_topic(topic='Base Gain Component', color='green', lines_or_markers='lines',
                                                pattern='dashdot')
        self.exchange.get_plot_data().set_topic(topic='Quote Gain Component', color='green', lines_or_markers='lines',
                                                pattern='dot')
        self.exchange.get_plot_data().set_topic(topic='MM Gain Component', color='green', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Big Bulls MM Gain', color='red', lines_or_markers='lines',
                                                pattern='dashdot')

        self.exchange.get_plot_data().set_topic(topic='Net MM Gain', color='cyan', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='Resultant Gain', color='purple', lines_or_markers='lines',
                                                pattern='solid')

        self.exchange.get_plot_data().set_topic(topic='Open Buy Count', color='magenta', lines_or_markers='lines',
                                                pattern='dashdot')
        self.exchange.get_plot_data().set_topic(topic='Open Sell Count', color='magenta', lines_or_markers='lines',
                                                pattern='dot')
        self.exchange.get_plot_data().set_topic(topic='Open Full Count', color='magenta', lines_or_markers='lines',
                                                pattern='solid')

    def register_plot_data(self, modified_time, usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity, **kwargs):
        usable_base_asset_data = {
            'topic': 'Usable Base Asset Balance ($)',
            'time': modified_time,
            'num': usable_base_asset,
        }

        usable_quote_asset_data = {
            'topic': 'Usable Quote Asset Balance ($)',
            'time': modified_time,
            'num': usable_quote_asset,
        }

        total_base_asset_data = {
            'topic': 'Total Base Asset Balance ($)',
            'time': modified_time,
            'num': total_base_asset,
        }

        total_quote_asset_data = {
            'topic': 'Total Quote Asset Balance ($)',
            'time': modified_time,
            'num': total_quote_asset,
        }

        usable_equity_data = {
            'topic': 'Usable Equity ($)',
            'time': modified_time,
            'num': usable_equity,
        }

        total_equity_data = {
            'topic': 'Total Equity ($)',
            'time': modified_time,
            'num': total_equity,
        }

        self.exchange.get_plot_data().add(**usable_base_asset_data)
        self.exchange.get_plot_data().add(**usable_quote_asset_data)
        self.exchange.get_plot_data().add(**total_base_asset_data)
        self.exchange.get_plot_data().add(**total_quote_asset_data)
        self.exchange.get_plot_data().add(**usable_equity_data)
        self.exchange.get_plot_data().add(**total_equity_data)

        for topic, value in kwargs.items():
            data = {
                'topic': topic,
                'time': modified_time,
                'num': value,
            }
            self.exchange.get_plot_data().add(**data)

    def place_order(self, order_type, order_side, price, size, curr_time):
        order = Order(
            quote_symbol=self.quote_symbol,
            base_symbol=self.base_symbol,
            order_type=order_type,
            order_side=order_side,
            price=price,
            size=size,
            time=curr_time
        )

        self.exchange.submit_order(order)

        if self.use_pom:
            self.pending_order_manager.register_order(order)

        if self.log_trade_activity:
            logger.info(f'[ORDER SUBMIT] {order_side} Trade submitted: {order}')

        self.order_states.add(order)

        return order

    def place_dual_orders(self, order_side, order_price, order_type, buy_tp_offset, sell_tp_offset, buy_sl_offset=None, sell_sl_offset=None, min_open_time=None, max_open_time=None):
        self.base_asset_balance, self.quote_asset_balance = self._get_balances()

        available_base_asset = self.base_asset_balance
        available_quote_asset = self.quote_asset_balance

        if order_side == "SELL":  # when sell condition is reached, the residual sell orders of executed buy orders are placed

            for order_id in list(self.buy_orders.keys()):
                buy_order = self.buy_orders[order_id]
                order_size = buy_order.size
                order_tp_price_th = buy_order.price + sell_tp_offset
                order_sl_price_th = None if sell_sl_offset is None  else (buy_order.price - sell_sl_offset)

                hit_tp = order_tp_price_th < order_price
                hit_sl = False if order_sl_price_th is None else order_sl_price_th > order_price
                hit_min_open_time = True if min_open_time is None else (self.curr_time - buy_order.get_state()["last_modified_time"]).total_seconds() > min_open_time
                hit_max_open_time = False if max_open_time is None else (self.curr_time - buy_order.get_state()["last_modified_time"]).total_seconds() > max_open_time

                # if order_tp_price_th < order_price and order_size < self.base_asset_balance:
                # if order_tp_price_th < order_price and available_base_asset - order_size > 0:
                # if (order_tp_price_th < order_price or (order_sl_price_th is not None and order_sl_price_th > order_price)) and available_base_asset - order_size > 0:
                if hit_min_open_time and (hit_tp or hit_sl or hit_max_open_time):
                    order = self.place_order(order_type=order_type,
                                             order_side="SELL",
                                             price=order_price if order_type == 'LIMIT' else None,
                                             size=order_size,
                                             curr_time=self.curr_time
                                             )

                    self.open_trades[order_id]['sell'] = order
                    del self.buy_orders[order_id]

                    available_base_asset -= order_size

        elif order_side == "BUY":  # when buy condition is reached, the residual buy orders of executed sell orders are placed

            for order_id in list(self.sell_orders.keys()):
                sell_order = self.sell_orders[order_id]
                order_size = sell_order.size
                order_tp_price_th = sell_order.price - buy_tp_offset
                order_sl_price_th = None if buy_sl_offset is None else (sell_order.price + buy_sl_offset)

                hit_tp = order_tp_price_th < order_price
                hit_sl = False if order_sl_price_th is None else order_sl_price_th > order_price
                hit_min_open_time = True if min_open_time is None else (self.curr_time - sell_order.get_state()["last_modified_time"]).total_seconds() > min_open_time
                hit_max_open_time = False if max_open_time is None else (self.curr_time - sell_order.get_state()["last_modified_time"]).total_seconds() > max_open_time

                order_value = order_size * order_price

                # if order_tp_price_th > order_price and order_value < self.quote_asset_balance:
                # if order_tp_price_th > order_price and available_quote_asset - order_value > 0:
                # if (order_tp_price_th > order_price or (order_sl_price_th is not None and order_sl_price_th < order_price)) and available_quote_asset - order_value > 0:
                if hit_min_open_time and (hit_tp or hit_sl or hit_max_open_time):
                    order = self.place_order(order_type=order_type,
                                             order_side="BUY",
                                             price=order_price if order_type == 'LIMIT' else None,
                                             size=order_size,
                                             curr_time=self.curr_time
                                             )
                    self.open_trades[order_id]['buy'] = order
                    del self.sell_orders[order_id]

                    available_quote_asset -= order_value

        return available_base_asset, available_quote_asset

    def check_execution(self, candle: Candle):
        # liquidation orders
        for liq_order_id in list(self.liquidation_orders.keys()):
            liq_order = self.liquidation_orders[liq_order_id]
            if liq_order.order_id in self.order_states.get('__filled_order_list'):
                del self.liquidation_orders[liq_order_id]

                if isinstance(liq_order.price, str):
                    liq_order.price = float(liq_order.price)

                if liq_order.order_side == "BUY":
                    self.order_stats["liq_buy"] += 1
                    self.single_order_completed_trades[liq_order.order_id] = {"buy": liq_order}
                else:
                    self.order_stats["liq_sell"] += 1
                    self.single_order_completed_trades[liq_order.order_id] = {"sell": liq_order}

                self.update_fee_tracker(liq_order)
                if self.verbose_completes:
                    logger.info(f'[LIQUIDATION COMPLETED] Order ID: {liq_order.order_id}')
            elif liq_order.order_id in self.order_states.get('__void_order_list'):
                del self.liquidation_orders[liq_order_id]
                if self.verbose_completes:
                    logger.info(f'[LIQUIDATION FAILED] Order ID: {liq_order.order_id}')
                self.rejected_order_ids[liq_order.order_id] = True
                logger.info(f"[LIQUIDATION FAILED] Order ID: {liq_order.order_id} {liq_order.order_status}: {liq_order}")

        # one-sided orders
        for single_order_id in list(self.open_one_sided_orders.keys()):
            single_order = self.open_one_sided_orders[single_order_id]
            if single_order.order_id in self.order_states.get('__filled_order_list'):
                del self.open_one_sided_orders[single_order_id]

                if isinstance(single_order.price, str):
                    single_order.price = float(single_order.price)

                if single_order.order_side == "BUY":
                    self.order_stats["buy_only"] += 1
                    self.single_order_completed_trades[single_order.order_id] = {"buy": single_order}
                else:
                    self.order_stats["sell_only"] += 1
                    self.single_order_completed_trades[single_order.order_id] = {"sell": single_order}

                self.update_fee_tracker(single_order)

                if single_order.order_type != "MARKET":
                    dt = self.get_order_exec_time(single_order)
                    self.order_exec_times[single_order.order_side].append(dt)

                if self.verbose_completes:
                    logger.info(f'[ONE-SIDED-ORDER COMPLETED] {single_order.order_side} Order ID: {single_order.order_id}')
            elif single_order.order_id in self.order_states.get('__void_order_list'):

                if self.max_residual_orders > 0:
                    self.add_to_residual_orders(ref_order=None, void_order=single_order)

                del self.open_one_sided_orders[single_order_id]
                if self.verbose_completes:
                    logger.info(f'[ONE-SIDED-ORDER FAILED] Order ID: {single_order.order_id}')
                self.rejected_order_ids[single_order.order_id] = True
                logger.info(f"[ONE-SIDED-ORDER FAILED] Order ID: {single_order.order_id} {single_order.order_status}: {single_order}")

        # dual orders
        for trade_id in list(self.open_trades.keys()):
            v = self.open_trades[trade_id]
            buy_order = v['buy']
            sell_order = v['sell']

            if buy_order is not None and sell_order is not None:
                # completed pair
                if buy_order.order_id in self.order_states.get(
                        '__filled_order_list') and sell_order.order_id in self.order_states.get('__filled_order_list'):
                    pnl = self.order_states.add_pair([buy_order, sell_order])
                    self.total_pnl += pnl
                    self.pnl_list.append(pnl)
                    self.pnl_percent_list.append(pnl / (buy_order.price * buy_order.size))
                    del self.open_trades[trade_id]
                    self.order_stats["buy_sell"] += 1

                    self.update_fee_tracker(buy_order)
                    self.update_fee_tracker(sell_order)
                    self.update_mm_gain_sub_components([buy_order, sell_order])

                    if buy_order.order_type != "MARKET":
                        dt = self.get_order_exec_time(buy_order)
                        self.order_exec_times[buy_order.order_side].append(dt)
                    if sell_order.order_type != "MARKET":
                        dt = self.get_order_exec_time(sell_order)
                        self.order_exec_times[sell_order.order_side].append(dt)

                    dt = self.get_trade_exec_time(buy_order, sell_order)
                    self.order_exec_times["BUY_SELL"].append(dt)

                    if self.verbose_completes:
                        logger.info(
                            f'[PAIR COMPLETED] (BUY-SELL) BUY: {buy_order.order_id}, SELL: {sell_order.order_id}, PnL={pnl}, Cum PnL={self.total_pnl}')

                elif buy_order.order_id in self.order_states.get(
                        '__filled_order_list') and sell_order.order_id in self.order_states.get('__void_order_list'):
                    pnl = self.order_states.add_pair([buy_order, sell_order])
                    self.total_pnl += pnl

                    if self.max_residual_orders > 0:
                        self.add_to_residual_orders(ref_order=buy_order, void_order=sell_order)

                    del self.open_trades[trade_id]
                    self.order_stats["buy_only"] += 1

                    self.update_fee_tracker(buy_order)

                    self.single_order_completed_trades[trade_id] = v

                    if buy_order.order_type != "MARKET":
                        dt = self.get_order_exec_time(buy_order)
                        self.order_exec_times[buy_order.order_side].append(dt)

                    if self.verbose_completes:
                        logger.info(
                            f'[PAIR COMPLETED] (BUY ONLY) BUY: {buy_order.order_id}, SELL: {sell_order.order_id}, PnL={pnl}, Cum PnL={self.total_pnl}')

                elif buy_order.order_id in self.order_states.get(
                        '__void_order_list') and sell_order.order_id in self.order_states.get('__filled_order_list'):
                    pnl = self.order_states.add_pair([buy_order, sell_order])
                    self.total_pnl += pnl

                    if self.max_residual_orders > 0:
                        self.add_to_residual_orders(ref_order=sell_order, void_order=buy_order)

                    del self.open_trades[trade_id]
                    self.order_stats["sell_only"] += 1

                    self.update_fee_tracker(sell_order)

                    self.single_order_completed_trades[trade_id] = v

                    if sell_order.order_type != "MARKET":
                        dt = self.get_order_exec_time(sell_order)
                        self.order_exec_times[sell_order.order_side].append(dt)

                    if self.verbose_completes:
                        logger.info(
                            f'[PAIR COMPLETED] (SELL ONLY) BUY: {buy_order.order_id}, SELL: {sell_order.order_id}, PnL={pnl}, Cum PnL={self.total_pnl}')

                elif buy_order.order_id in self.order_states.get(
                        '__void_order_list') and sell_order.order_id in self.order_states.get('__void_order_list'):
                    del self.open_trades[trade_id]
                    if self.verbose_completes:
                        logger.info(
                            f'[PAIR COMPLETED] (NOTHING) BUY: {buy_order.order_id}, SELL: {sell_order.order_id}, PnL=0, Cum PnL={self.total_pnl}')

                # remove the following two elif statements later
                elif buy_order.order_id in self.order_states.get('__filled_order_list'):
                    if isinstance(buy_order.price, str):
                        buy_order.price = float(buy_order.price)
                    # if self.verbose_completes:
                    #     logger.info(f'[BUY COMPLETED] {buy_order.order_id} {buy_order}')

                elif sell_order.order_id in self.order_states.get('__filled_order_list'):
                    if isinstance(sell_order.price, str):
                        sell_order.price = float(sell_order.price)
                    # if self.verbose_completes:
                    #     logger.info(f'[SELL COMPLETED] {sell_order.order_id} {sell_order}')

                elif sell_order.order_id in self.order_states.get('__void_order_list') and sell_order.order_id not in self.rejected_order_ids:
                    self.rejected_order_ids[sell_order.order_id] = True
                    logger.info(f"[SELL ORDER FAILED] Order ID: {sell_order.order_id} {sell_order.order_status}: {sell_order}, order size: {sell_order.size}, base: {self.base_asset_balance}, quote: {self.quote_asset_balance}")

                    if buy_order.order_id in self.order_states.get('__open_order_list'):
                        self.exchange.cancel_order(buy_order)
                        logger.info(f"[BUY ORDER CANCELLATION] Order ID: {buy_order.order_id} Cancellation of dual order")

                elif buy_order.order_id in self.order_states.get('__void_order_list') and buy_order.order_id not in self.rejected_order_ids:
                    self.rejected_order_ids[buy_order.order_id] = True
                    logger.info(f"[BUY ORDER FAILED] Order ID: {buy_order.order_id} {buy_order.order_status}: {buy_order}, order value: {buy_order.price * buy_order.size}, base: {self.base_asset_balance}, quote: {self.quote_asset_balance}")

                    if sell_order.order_id in self.order_states.get('__open_order_list'):
                        self.exchange.cancel_order(sell_order)
                        logger.info(f"[SELL ORDER CANCELLATION] Order ID: {sell_order.order_id} Cancellation of dual order")

            elif buy_order is not None:
                if buy_order.order_id in self.order_states.get('__filled_order_list'):
                    if isinstance(buy_order.price, str):
                        buy_order.price = float(buy_order.price)
                    # if self.verbose_completes:
                    #     logger.info(f'[BUY COMPLETED] {buy_order.order_id} {buy_order}')
                    self.buy_orders[buy_order.order_id] = buy_order

                elif buy_order.order_id in self.order_states.get(
                        '__void_order_list') and buy_order.order_id not in self.rejected_order_ids:
                    self.rejected_order_ids[buy_order.order_id] = True
                    logger.info(
                        f"[BUY ORDER FAILED] Order ID: {buy_order.order_id} {buy_order.order_status}: {buy_order}, order value: {buy_order.price * buy_order.size}, base: {self.base_asset_balance}, quote: {self.quote_asset_balance}")

                    del self.open_trades[trade_id]

            elif sell_order is not None:
                if sell_order.order_id in self.order_states.get('__filled_order_list'):
                    if isinstance(sell_order.price, str):
                        sell_order.price = float(sell_order.price)
                    # if self.verbose_completes:
                    #     logger.info(f'[SELL COMPLETED] {sell_order.order_id} {sell_order}')
                    self.sell_orders[sell_order.order_id] = sell_order

                elif sell_order.order_id in self.order_states.get(
                        '__void_order_list') and sell_order.order_id not in self.rejected_order_ids:
                    self.rejected_order_ids[sell_order.order_id] = True
                    logger.info(
                        f"[SELL ORDER FAILED] Order ID: {sell_order.order_id} {sell_order.order_status}: {sell_order}, order size: {sell_order.size}, base: {self.base_asset_balance}, quote: {self.quote_asset_balance}")

                    del self.open_trades[trade_id]

    def get_dual_order(self, primal_order: Order):
        is_buy = primal_order.order_side == "BUY"
        order_id = primal_order.order_id

        for k, v in self.open_trades.items():
            buy_order = v["buy"]
            sell_order = v["sell"]

            if is_buy and (buy_order is not None) and buy_order.order_id == order_id:
                return sell_order
            elif not is_buy and (sell_order is not None) and sell_order.order_id == order_id:
                return buy_order

    def get_all_open_orders(self):
        return list(self.order_states.get("__open_order_list").values())

    def get_open_order_counts(self):
        """
        Get the current open order counts of each order sides
        """

        open_buy_count = 0
        open_sell_count = 0

        all_open_orders = self.get_all_open_orders()

        for open_order in all_open_orders:
            if open_order.order_side == "BUY":
                open_buy_count += 1
            else:
                open_sell_count += 1

        return open_buy_count, open_sell_count, (open_buy_count + open_sell_count)

    def calculate_pending_profit_component(self):
        """
        Calculate the pending_component at a given time. The total equity gain at a given time is given by,
            total_gain(t) = holding_cost(t) + pending_component(t) + mm_gain(t)

            Where,
            pending_component(t) = [half_sell_earned_quote(t) - half_buy_spent_quote(t)] +
                        [half_buy_amount_base(t) - half_sell_amount_base(t)] * mid_price(t)
        """
        # TODO: orders_per_trade - remove this to handle any arbitrary no of orders per trade

        mid_price = self.close
        half_buy_amount_base = 0
        half_sell_amount_base = 0
        half_sell_earned_quote = 0
        half_buy_spent_quote = 0

        # TODO: add one sided completed orders and completed liquidation orders
        for _, trade in {**self.open_trades, **self.single_order_completed_trades}.items():
            tr_orders = [trade[k] for k in trade if k != "ts"]
            executed_orders = [tr_ord for tr_ord in tr_orders if (tr_ord is not None and tr_ord.filled_size > 0)]

            if (len(tr_orders) > len(executed_orders)) or (len(tr_orders) == 1 and len(executed_orders) == 1):

                for exec_order in executed_orders:

                    delta_base, delta_quote, _, _ = self.find_asset_deltas(exec_order, return_abs=True)

                    if exec_order.order_side == "BUY":
                        half_buy_spent_quote += delta_quote
                        half_buy_amount_base += delta_base

                    elif exec_order.order_side == "SELL":
                        half_sell_earned_quote += delta_quote
                        half_sell_amount_base += delta_base

        fee_component = self.order_fee_tracker["quote"] + self.order_fee_tracker["base"] * mid_price
        pending_components = [half_buy_amount_base * mid_price, half_sell_amount_base * mid_price, half_buy_spent_quote,
                              half_sell_earned_quote, fee_component]
        pending_order_counts = self.get_open_order_counts()

        return pending_components, pending_order_counts

    def update_mm_gain_sub_components(self, order_pair):
        tr_orders = order_pair
        executed_orders = [tr_ord for tr_ord in tr_orders if (tr_ord.filled_size > 0)]

        if len(tr_orders) == len(executed_orders) and len(executed_orders) > 1:
            for ex_order in executed_orders:
                delta_base, delta_quote, _, _ = self.find_asset_deltas(ex_order)
                self.mm_gain_sub_component_tracker["base"] += delta_base
                self.mm_gain_sub_component_tracker["quote"] += delta_quote

    def calculate_mm_gain_component(self):
        # TODO: The reason for the difference of mm_gain_component and the Net Profit (PnL) is that, PnL is calculated based on the executed price but mm_gain_component is always calculated based on the current market price
        mid_price = self.close
        mm_gain_component = [self.mm_gain_sub_component_tracker["quote"],
                             mid_price * self.mm_gain_sub_component_tracker["base"]]

        return mm_gain_component

    def calculate_profit_components(self):
        holding_component = (self.equity_stats['init_base'] + self.equity_stats['init_holding_base']) * (
                    self.close - self.equity_stats['init_price'])
        pending_components, pending_order_counts = self.calculate_pending_profit_component()
        mm_gain_component = self.calculate_mm_gain_component()

        return holding_component, pending_components, pending_order_counts, mm_gain_component

    def update_fee_tracker(self, order: Order):
        _, _, fees_base, fees_quote = self.find_asset_deltas(order)

        self.order_fee_tracker["quote"] += fees_quote
        self.order_fee_tracker["base"] += fees_base

    def add_to_residual_orders(self, ref_order: Order, void_order: Order):
        """
        Add incompletely executed dual orders for later execution
        Args:
            ref_order: fully executed order
            void_order: failed order
        """

        if void_order.order_side == "BUY" or (ref_order is not None and ref_order.order_side == "SELL"):
            self.residual_sell_orders[void_order.order_id] = {
                "price": void_order.price,
                "size": ref_order.filled_size if ref_order is not None else void_order.size,
                "order_id": ref_order.order_id if ref_order is not None else void_order.order_id
            }
        elif void_order.order_side == "SELL" or (ref_order is not None and ref_order.order_side == "BUY"):
            self.residual_buy_orders[void_order.order_id] = {
                "price": void_order.price,
                "size": ref_order.filled_size if ref_order is not None else void_order.size,
                "order_id": ref_order.order_id if ref_order is not None else void_order.order_id
            }

    def plot_profit_components(self, curr_time):
        holding_component, pending_components, pending_order_counts, mm_gain_components = self.calculate_profit_components()

        (half_buy_value_base, half_sell_value_base, half_buy_spent_quote, half_sell_earned_quote, fee_component) = pending_components
        half_buy_component = (half_buy_value_base - half_buy_spent_quote)
        half_sell_component = (half_sell_earned_quote - half_sell_value_base)
        pending_component = half_buy_component + half_sell_component

        quote_gain_component, base_gain_component = mm_gain_components
        mm_gain_component = quote_gain_component + base_gain_component

        net_mm_gain_component = pending_component + mm_gain_component
        resultant_gain = holding_component + net_mm_gain_component

        big_bulls_mm_gain = half_sell_component + mm_gain_component  # big-bulls mm gain

        open_buy_count, open_sell_count, full_count = pending_order_counts

        values_list = [holding_component,
                       half_buy_component, half_sell_component, pending_component,
                       fee_component,
                       quote_gain_component, base_gain_component, mm_gain_component,
                       net_mm_gain_component, resultant_gain, big_bulls_mm_gain,
                       open_buy_count, open_sell_count, full_count]

        topics_list = ['Holding Component',
                       'Half Buy Pending Component', 'Half Sell Pending Component', 'Pending Component',
                       'Fee Component',
                       'Base Gain Component', 'Quote Gain Component', 'MM Gain Component',
                       'Net MM Gain', 'Resultant Gain', 'Big Bulls MM Gain',
                       'Open Buy Count', 'Open Sell Count', 'Open Full Count']

        for value, topic in zip(values_list, topics_list):
            data = {
                'topic': topic,
                'time': curr_time,
                'num': value,
            }
            self.exchange.get_plot_data().add(**data)

    @staticmethod
    def find_asset_deltas(c_order: Order, return_abs=False):
        """
        Returns the base and quote assets changes caused by a completed order along with the incurred fees
        """

        ord_type = c_order.order_type  # LIMIT/MARKET
        ord_side = c_order.order_side  # BUY/SELL

        ord_size = c_order.filled_size
        ord_price = c_order.price
        ord_value = ord_size * ord_price

        ord_fees = c_order.fees
        fees_base = ord_fees["base_fee"]
        fees_quote = ord_fees["quote_fee"]

        if ord_side == "BUY":
            delta_base = ord_size - fees_base
            delta_quote = -(ord_value + fees_quote)

        else:  # SELL
            delta_base = -ord_size
            delta_quote = ord_value - fees_quote

        if return_abs:
            return abs(delta_base), abs(delta_quote), fees_base, fees_quote
        else:
            return delta_base, delta_quote, fees_base, fees_quote

    def _check_asset_imbalance_ratio(self, bid, ask, free_base_asset_balance, free_quote_asset_balance):
        """
        Check the asset imbalance using the ratio between two assets
        """

        mid_price = (bid + ask) / 2
        asset_ratio = free_base_asset_balance * mid_price / (free_quote_asset_balance + 1e-6)
        drift = self.init_asset_ratio / (asset_ratio + 1e-6)

        return asset_ratio, drift

    def _liquidate_assets(self, free_base_asset_balance, free_quote_asset_balance, side, liquidating_percentage, curr_time):
        """
        Liquidate accumulating assets
        """
        assert side in ["BUY", "SELL"]

        if side == "BUY":
            value = free_quote_asset_balance * liquidating_percentage
            size = value / self.ask

        else:
            size = free_base_asset_balance * liquidating_percentage
            value = size * self.bid

        if value >= self.min_notional:
            liquidation_order = self.place_order(order_type="MARKET", order_side=side, price=None, size=size,
                                                 curr_time=curr_time)
            self.liquidation_orders[liquidation_order.order_id] = liquidation_order
            if self.verbose:
                logger.info(f'[LIQUIDATION] Order Placed {side} order: {liquidation_order}')
        else:
            rough_price = self.ask if size == 'BUY' else self.bid
            logger.debug(f"[SKIPPING-LIQUIDATION] Liquidation order value {value} ({size} @ {rough_price}) is less than the minimum notional {self.min_notional}")

    def _get_equity_balance(self):
        # TODO: Verify balance calculations
        usable_base_asset = self.base_asset_balance * self.close
        usable_quote_asset = self.quote_asset_balance
        total_base_asset = (self.base_asset_balance + self.pending_base_asset_amount) * self.close
        total_quote_asset = self.quote_asset_balance + self.pending_quote_asset_amount
        usable_equity = self.base_asset_balance * self.close + self.quote_asset_balance
        total_equity = total_base_asset + total_quote_asset

        return usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity

    def _get_balances(self):
        balance = self.exchange.get_wallet_balance()
        return balance[self.base_symbol].free, balance[self.quote_symbol].free

    def _pending_wallet_balances(self):
        """
        Get the base and quote assert values stuck by open trades
        """

        balance = self.exchange.get_wallet_balance()
        return balance[self.base_symbol].holding, balance[self.quote_symbol].holding

    def _get_metric_report(self):

        # completed order count
        completed_order_count = self.order_stats['buy_sell'] * 2 + self.order_stats['buy_only'] + self.order_stats[
            'sell_only'] + self.order_stats['liq_buy'] + self.order_stats['liq_sell']

        # trade time info
        trading_time = (self.curr_time - self.start_time).total_seconds()
        trades_per_hour = self.order_stats['buy_sell'] / (trading_time / 3600)

        buy_exec_times = self.order_exec_times["BUY"]
        sell_exec_times = self.order_exec_times["SELL"]
        buy_sell_exec_times = self.order_exec_times["BUY_SELL"]

        # PnL calculations
        pnl_percentiles = find_percentiles(self.pnl_list) if len(self.pnl_list) > 0 else None
        pnl_percent_percentiles = find_percentiles(self.pnl_percent_list) if len(
            self.pnl_percent_list) > 0 else None
        sharp_ratio = find_sharp_ratio(self.pnl_percent_list, trading_days=trading_time / (24 * 3600))

        pnl_array = np.array(self.pnl_list)
        profitable_trades = pnl_array[pnl_array > 0]
        losing_trades = pnl_array[pnl_array < 0]
        neutral_trades = pnl_array[pnl_array == 0]

        profitable_trade_count = len(profitable_trades)
        losing_trade_count = len(losing_trades)
        neutral_trade_count = len(neutral_trades)

        total_profit = np.sum(profitable_trades)
        total_loss = abs(np.sum(losing_trades))
        net_profit = total_profit - total_loss
        net_profit_percent = net_profit / self.equity_stats["init_quote"]

        # price change
        price_diff = self.equity_stats['last_price'] - self.equity_stats['init_price']

        # base asset gains
        total_init_base = self.equity_stats['init_base'] + self.equity_stats['init_holding_base']
        total_last_base = self.equity_stats['last_base'] + self.equity_stats['last_holding_base']
        init_base_in_quote = total_init_base * self.equity_stats['init_price']
        last_base_in_quote = total_last_base * self.equity_stats['last_price']
        base_gain = total_last_base - total_init_base
        base_gain_in_quote = last_base_in_quote - init_base_in_quote  # TODO: or base_gain * self.equity_stats['last_price'] --> base_gain x last_price ?

        # quote asset gains
        total_init_quote = self.equity_stats['init_quote'] + self.equity_stats['init_holding_quote']
        total_last_quote = self.equity_stats['last_quote'] + self.equity_stats['last_holding_quote']
        quote_gain = total_last_quote - total_init_quote

        # equity gains
        init_equity = total_init_quote + init_base_in_quote
        last_equity = total_last_quote + last_base_in_quote
        equity_gain = last_equity - init_equity
        last_equity_no_trade = total_init_quote + total_init_base * self.equity_stats['last_price']
        equity_gain_no_trade = last_equity_no_trade - init_equity
        trade_advantage = equity_gain - equity_gain_no_trade

        metric_report_str = ""

        metric_report_str += "==" * 50 + "\n"
        metric_report_str += "||" * 16 + " Trade Report from Metric Evaluator " + "||" * 16 + "\n"
        metric_report_str += "==" * 50 + "\n"

        # ---------------------------------------
        metric_report_str += f"\n{BColors.BOLD}{BColors.HEADER}1) Basic Info{BColors.ENDC}\n" + "\n"

        metric_report_str += f"\t> # of open buy-sell pairs: {len(self.open_trades)}" + "\n"
        metric_report_str += f"\t> # of open one-sided orders: {len(self.open_one_sided_orders)}" + "\n"
        metric_report_str += f"\t> # of open liquidation orders: {len(self.liquidation_orders)}" + "\n"
        metric_report_str += f"\t> # of completed orders: {completed_order_count}" + "\n"
        metric_report_str += f"\t> # of rejected orders: {len(self.rejected_order_ids)}" + "\n"

        if completed_order_count > 0:
            metric_report_str += f"\t\t> buy-sell count: {self.order_stats['buy_sell'] * 2} ({self.order_stats['buy_sell'] * 2 * 100 / completed_order_count:.4f} %)" + "\n"
            metric_report_str += f"\t\t> one-sided count: {self.order_stats['buy_only'] + self.order_stats['sell_only']} ({(self.order_stats['buy_only'] + self.order_stats['sell_only']) * 100 / completed_order_count:.4f} %)" + "\n"
            metric_report_str += f"\t\t\t> buy only count: {self.order_stats['buy_only']} ({self.order_stats['buy_only'] * 100 / completed_order_count:.4f} %)" + "\n"
            metric_report_str += f"\t\t\t> sell only count: {self.order_stats['sell_only']} ({self.order_stats['sell_only'] * 100 / completed_order_count:.4f} %)" + "\n"
            metric_report_str += f"\t\t> Liquidation order count: {self.order_stats['liq_buy'] + self.order_stats['liq_sell']} (buy: {self.order_stats['liq_buy']}, sell: {self.order_stats['liq_sell']})" + "\n"

            metric_report_str += f"\t> Start time: {self.start_time}" + "\n"
            metric_report_str += f"\t> End time: {self.curr_time}" + "\n"
            metric_report_str += f"\t> Trading time: {trading_time / 60:.2f} minutes ({trading_time / 3600:.2f} hours = {trading_time / (24 * 3600):.2f} days)" + "\n"
            metric_report_str += "\t> Trades (Buy-Sell Pair) Execution Times:" + "\n"
            metric_report_str += f"\t\t> Trading rate: {trades_per_hour: .1f} trades per hour = {int(trades_per_hour * 24)} trades per day" + "\n"
            if buy_sell_exec_times:
                metric_report_str += f"\t\t> Longest trade time: {np.max(buy_sell_exec_times) / 60: .2f} minutes = {np.max(buy_sell_exec_times) / 3600: .2f} hours" + "\n"
                metric_report_str += f"\t\t> Shortest trade time: {np.min(buy_sell_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> Average trade time: {np.mean(buy_sell_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> STD of trade time: {np.std(buy_sell_exec_times) / 60: .2f} minutes" + "\n"
                # metric_report_str += f"\t\t> Trade time sequence: {get_order_ts(buy_sell_exec_times)}")  # Used for debugging
                metric_report_str += f"\t\t> Trade time percentiles: {find_percentiles(buy_sell_exec_times, time_list=True, time_scale_by_60=True)} minutes" + "\n"

            if buy_exec_times:
                metric_report_str += "\t> Buy Execution Times (Limit Orders Only):" + "\n"
                metric_report_str += f"\t\t> Longest buy time: {np.max(buy_exec_times) / 60: .2f} minutes = {np.max(buy_sell_exec_times) / 3600: .2f} hours" + "\n"
                metric_report_str += f"\t\t> Shortest buy time: {np.min(buy_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> Average buy time: {np.mean(buy_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> STD of buy time: {np.std(buy_exec_times) / 60: .2f} minutes" + "\n"
                # metric_report_str += f"\t\t> Buy time sequence: {get_order_ts(buy_exec_times)}")  # Used for debugging
                metric_report_str += f"\t\t> Buy time percentiles: {find_percentiles(buy_exec_times, time_list=True, time_scale_by_60=True)} minutes" + "\n"

            if sell_exec_times:
                metric_report_str += "\t> Sell Execution Times (Limit Orders Only):" + "\n"
                metric_report_str += f"\t\t> Longest sell time: {np.max(sell_exec_times) / 60: .2f} minutes = {np.max(buy_sell_exec_times) / 3600: .2f} hours" + "\n"
                metric_report_str += f"\t\t> Shortest sell time: {np.min(sell_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> Average sell time: {np.mean(sell_exec_times) / 60: .2f} minutes" + "\n"
                metric_report_str += f"\t\t> STD of sell time: {np.std(sell_exec_times) / 60: .2f} minutes" + "\n"
                # metric_report_str += f"\t\t> Sell time sequence: {get_order_ts(sell_exec_times)}")  # Used for debugging
                metric_report_str += f"\t\t> Sell time percentiles: {find_percentiles(sell_exec_times, time_list=True, time_scale_by_60=True)} minutes" + "\n"

            # ---------------------------------------
            metric_report_str += f"\n{BColors.BOLD}{BColors.HEADER}2) PnL stats (From Completed buy-sell trades){BColors.ENDC}\n" + "\n"

            # metric_report_str += f"\t> PnL sequence {self.quote_symbol}: {np.round(self.pnl_completed_trades, 2)}" + "\n"
            # metric_report_str += f"\t> PnL sequence %: {self.pnl_percent_completed_trades * 100}" + "\n"
            metric_report_str += f"\t> Average PnL {self.quote_symbol}: {self.quote_symbol} {np.mean(self.pnl_list):.5f}" + "\n"
            metric_report_str += f"\t> Average PnL %: {np.mean(self.pnl_percent_list) * 100:.3f}" + "\n"
            metric_report_str += f"\t> STD of PnL {self.quote_symbol}: {self.quote_symbol} {np.std(self.pnl_list):.5f}" + "\n"
            metric_report_str += f"\t> STD of PnL %: {np.std(self.pnl_percent_list) * 100:.3f}" + "\n"
            metric_report_str += f"\t> PnL percentiles {self.quote_symbol}: {pnl_percentiles}" + "\n"
            metric_report_str += f"\t> PnL percentiles %: {pnl_percent_percentiles}" + "\n"
            metric_report_str += f"\t> Sharpe ratio: {sharp_ratio:.5f}" + "\n"
            metric_report_str += f"\t> # of profitable trades: {profitable_trade_count}" + "\n"
            metric_report_str += f"\t> # of losing trades: {losing_trade_count}" + "\n"
            metric_report_str += f"\t> # of neutral trades: {neutral_trade_count}" + "\n"
            metric_report_str += f"\t> Profitable trade %: {profitable_trade_count * 100 / self.order_stats['buy_sell'] if self.order_stats['buy_sell'] > 0 else 0:.1f}" + "\n"
            metric_report_str += f"\t> Losing trade %: {losing_trade_count * 100 / self.order_stats['buy_sell'] if self.order_stats['buy_sell'] > 0 else 0:.1f}" + "\n"
            metric_report_str += f"\t> Total gain: {self.quote_symbol} {total_profit:.5f}" + "\n"
            metric_report_str += f"\t> Total loss: {self.quote_symbol} {total_loss:.5f}" + "\n"
            metric_report_str += f"\t> Net profit: {BColors.BOLD}{self.quote_symbol} {net_profit:.5f}{BColors.ENDC}" + "\n"
            metric_report_str += f"\t> Net profit %: {BColors.BOLD} {net_profit_percent * 100:.5f} %{BColors.ENDC}" + "\n"

            metric_report_str += f"\n{BColors.BOLD}{BColors.HEADER}3) Symbol Gains (From all trades - Including open order quantities){BColors.ENDC}\n" + "\n"

            metric_report_str += f"\t> Starting Price: {self.quote_symbol} {self.equity_stats['init_price']}" + "\n"
            metric_report_str += f"\t> Last Price: {self.quote_symbol} {self.equity_stats['last_price']}" + "\n"
            metric_report_str += f"\t> Price Difference: {self.quote_symbol} {price_diff:.5f} ({price_diff * 100 / self.equity_stats['init_price']:.5f} %)" + "\n"

            metric_report_str += f"\t> {self.base_symbol} initial value: {total_init_base} (free: {self.equity_stats['init_base']:.5f}, holding: {self.equity_stats['init_holding_base']:.5f})" + "\n"
            metric_report_str += f"\t> {self.base_symbol} last value: {total_last_base} (free: {self.equity_stats['last_base']:.5f}, holding: {self.equity_stats['last_holding_base']:.5f})" + "\n"
            metric_report_str += f"\t> {self.base_symbol} initial quote value: {self.quote_symbol} {init_base_in_quote:.5f}" + "\n"
            metric_report_str += f"\t> {self.base_symbol} ending quote value: {self.quote_symbol} {last_base_in_quote:.5f}" + "\n"
            # if self.init_sym1_in_quote > 0:
            metric_report_str += f"\t> {self.base_symbol} gain: {BColors.BOLD}{base_gain:.5f} = {self.quote_symbol} {base_gain_in_quote:.5f} ({base_gain_in_quote * 100 / (init_base_in_quote + 1e-9):.5f} %) --> Considering Price Fluctuation{BColors.ENDC}" + "\n"
            metric_report_str += f"\t> {self.base_symbol} gain: {BColors.BOLD}{base_gain:.5f} = {self.quote_symbol} {base_gain * self.equity_stats['last_price']:.5f} ({base_gain * self.equity_stats['last_price'] * 100 / (init_base_in_quote + 1e-9):.5f} %) --> Omitting Price Fluctuation{BColors.ENDC}\n" + "\n"


            metric_report_str += f"\t> {self.quote_symbol} initial value: {total_init_quote} (free: {self.equity_stats['init_quote']:.5f}, holding: {self.equity_stats['init_holding_quote']:.5f})" + "\n"
            metric_report_str += f"\t> {self.quote_symbol} last value: {total_last_quote} (free: {self.equity_stats['last_quote']:.5f}, holding: {self.equity_stats['last_holding_quote']:.5f})" + "\n"
            metric_report_str += f"\t> {self.quote_symbol} gain: {BColors.BOLD}{self.quote_symbol} {quote_gain:.5f} ({quote_gain * 100 / (total_init_quote + 1e-12):.5f} %){BColors.ENDC}\n" + "\n"

            metric_report_str += f"\t> Initial equity value: {self.quote_symbol} {init_equity:.5f}" + "\n"
            metric_report_str += f"\t> Ending equity value: {self.quote_symbol} {last_equity:.5f}" + "\n"
            metric_report_str += f"\t> No Trade Ending equity value (expected): {self.quote_symbol} {last_equity_no_trade:.5f}" + "\n"
            # if self.init_equity > 0:
            metric_report_str += f"\t> Equity gain: {BColors.BOLD}{self.quote_symbol} {equity_gain:.5f} ({equity_gain * 100 / init_equity:.5f} %) {BColors.ENDC}" + "\n"
            metric_report_str += f"\t> No Trade Equity gain (expected): {BColors.BOLD}{self.quote_symbol} {equity_gain_no_trade:.5f} ({equity_gain_no_trade * 100 / init_equity:.5f} %) {BColors.ENDC}" + "\n"
            metric_report_str += f"\t> Trading Advantage: {BColors.BOLD}{self.quote_symbol} {trade_advantage:.5f} ({trade_advantage * 100 / init_equity:.5f} %) {BColors.ENDC}" + "\n"

        logger.info(metric_report_str)

    @staticmethod
    def get_order_exec_time(order: Order):
        """
        Get the order time
        Args:
            order: order object

        Returns: order time in seconds
        """
        order_state = order.get_state(is_thread_safe=False)
        dt = (order_state["last_modified_time"] - order_state["time"]).total_seconds()

        return dt

    @staticmethod
    def get_trade_exec_time(buy_order: Order, sell_order: Order):
        """
        Get the trade (order pair) time
        Args:
            buy_order: buy order object
            sell_order: sell order object

        Returns: trade time in seconds
        """
        buy_order_state = buy_order.get_state(is_thread_safe=False)
        sell_order_state = sell_order.get_state(is_thread_safe=False)

        t_start = min(buy_order_state["time"], sell_order_state["time"])
        t_end = min(buy_order_state["last_modified_time"], sell_order_state["last_modified_time"])

        dt = (t_end - t_start).total_seconds()

        return dt

    @staticmethod
    def get_min_profitable_spread(mid_price, fee_rate):
        """
        Calculate the minimum spread between an order pair to make the trade profitable when fees are applied
        """
        return mid_price * fee_rate / (1 - fee_rate)
