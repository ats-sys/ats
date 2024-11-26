import torch

from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.candle import Candle
from ats.utils.general import helpers as general_helpers
from ats.state.order_state_list_state import OrderStateListState
from ats.strategies.advanced_base_strategy import AdvancedBaseStrategy
from ats.exceptions.general_exceptions import ConfigValidationException
from ats.strategies.lstm_strategy.model import ATSModel


class Strategy(AdvancedBaseStrategy):
    """
    Place buy and sell orders using an AI model signal + RSI or OBV
    - This strategy can trade both long and short models. (go_long and go_short parameters. Default go_long: True, go_short: False)
    - Take the primary buy-sell signal using the AI model output.
        - ai_val: 1 -> Buy Signal
        - ai_val: 2 -> Sell Signal
    - We confirm that buy-sell signals using a secondary signal, here we use either RSI or OBV signal
        - in the config if use_obv: True -> use OBV signal, else sue RSI signal (default use_obv: False -> RSI)
        - OBV:
            - if current timestep OBV change is the maximum of the last obv_window_length OBV changes -> Buy Signal
            - if current timestep OBV change is the minimum of the last obv_window_length OBV changes -> Sell Signal
        - RSI:
            - if RSI > 100 + rsi_d -> Buy Signal
            - if RSI < rsi_d -> Sell Signal
    - The exit conditions are based on take-profit, stop-loss levels.
        - tp_multiple and sl_multiple decides the tp and sl levels as a multiple of the volatility
    """

    def __init__(self, config, state: SimpleState = None):
        super().__init__(config, state)

        self.log_trade_activity = self.config['log_trade_activity']

        self.std_window_length = self.config["std_window_length"]
        self.ai_window_length = self.config["ai_window_length"]
        self.rsi_d = self.config.get("rsi_d", 20)
        rsi_candle_length = self.config.get("rsi_candle_length", 1)
        ai_candle_length = self.config.get("ai_candle_length", 1)
        self.obv_window_length = self.config["obv_window_length"]
        self.use_obv = self.config.get("use_obv", False)
        self.go_long = self.config.get("go_long", True)
        self.go_short = self.config.get("go_short", False)
        # self.min_open_time = self.config.get("min_open_time", 5 * 60)
        self.dual_order_check_interval = self.config.get("dual_order_check_interval", 60)

        self.max_residual_orders = self.config.get("max_residual_orders", 0)
        self.max_one_side_buy_orders = self.config.get("max_one_side_buy_orders", 0)
        self.max_one_side_sell_orders = self.config.get("max_one_side_sell_orders", 0)

        self.tp_multiple = self.config.get("tp_multiple", 2)
        self.sl_multiple = self.config.get("sl_multiple", 6)

        self.order_states = OrderStateListState()

        ai_model_kwargs = {
            "n_inputs": 2,
            "hidden_size": 50,
            "num_layers": 2,
            "n_classes": 3,
        }
        weight_path = self.config.get("ai_weight_path", "ai_model_clf.pt")
        ai_model = self.load_ai_model(ATSModel, weight_path, **ai_model_kwargs)

        self.ai_indicator = general_helpers.get_class_from_namespace("indicators:ai_indicator")({'N': self.ai_window_length, 'candle_length': ai_candle_length, 'model': ai_model})
        self.std_indicator = general_helpers.get_class_from_namespace("indicators:std_indicator")({'N': self.std_window_length})
        self.rsi_indicator = general_helpers.get_class_from_namespace("indicators:rsi_indicator")({'N': 14, "candle_length": rsi_candle_length})
        self.obv_indicator = general_helpers.get_class_from_namespace("indicators:obv_indicator")({'N': None, 'candle_length': ai_candle_length})

        self.order_value_pct = self.config["order_value_pct"] / 100

        self.std = None
        self.ai_val = None
        self.rsi = None
        self.obv = None
        self.obv_diff = None

        self.last_dual_order_check_time = None

        self.obv_diff_list = []

    @staticmethod
    def load_ai_model(model_class, weight_path, **model_kwargs):
        model = model_class(**model_kwargs)
        model.load_state_dict(torch.load(weight_path, weights_only=True))
        model.eval()

        return model

    def init_plots(self):
        super().init_plots()

        self.exchange.get_plot_data().set_topic(topic='RSI', color='purple', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='OBV', color='blue', lines_or_markers='lines',
                                                pattern='solid')
        self.exchange.get_plot_data().set_topic(topic='AI Indicator', color='red', lines_or_markers='lines',
                                                pattern='solid')

    # Implemented the base class abstract method
    def validate_config(self) -> None:
        required_properties = ['base_symbol', 'quote_symbol']

        for prop in required_properties:
            if prop not in self.config:
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

    # Implemented the base class abstract method
    def on_candle(self, candle: Candle) -> None:
        self.base_asset_balance, self.quote_asset_balance = self._get_balances()
        self.pending_base_asset_amount, self.pending_quote_asset_amount = self._pending_wallet_balances()
        self.close = candle.close
        self.curr_time = candle.time
        self.bid = self.close
        self.ask = self.close

        if self.start_time is None:
            self.start_time = self.curr_time
            self.init_asset_ratio = self.base_asset_balance * candle.close / (self.quote_asset_balance + 1e-6)
            self.last_dual_order_check_time = self.curr_time.timestamp()

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

        self.update_indicators(candle)
        # self.__update_side()

        usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity = self._get_equity_balance()

        extra_plot_data = {'RSI': self.rsi, 'OBV': self.obv, 'AI Indicator': self.ai_val}
        self.register_plot_data(self.curr_time, usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity, **extra_plot_data)

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

            do_place_order, order_side = self._is_place_order_condition_true()

            if do_place_order or (self.curr_time.timestamp() - self.last_dual_order_check_time > self.dual_order_check_interval):
                self.check_and_place_orders(do_place_order, order_side)
            # else:
            #     # To indicate that the program is running, print dots while waiting for buy condition
            #     if num_open_trades == 0:
            #         print(". ", end="", flush=True)

        self.order_states.update()
        self.check_execution(candle)
        self.plot_profit_components(self.curr_time)

    def check_and_place_orders(self, do_place_order, order_side, order_type="MARKET"):

        available_base_asset, available_quote_asset = self.base_asset_balance, self.quote_asset_balance

        limit_buy_price = self.close - self.std / 4
        limit_sell_price = self.close + self.std / 4

        if  self.go_short:
            # check and place the dual orders of already placed sell orders
            available_base_asset, available_quote_asset = self.place_dual_orders(order_side="BUY", order_price=limit_buy_price, order_type=order_type, buy_tp_offset=self.tp_multiple * self.std, sell_tp_offset=self.tp_multiple * self.std, buy_sl_offset=self.sl_multiple * self.std, sell_sl_offset=self.sl_multiple * self.std, min_open_time=None, max_open_time=None)

        if  self.go_long:
            # check and place the dual orders of already placed buy orders
            available_base_asset, available_quote_asset = self.place_dual_orders(order_side="SELL", order_price=limit_sell_price, order_type=order_type, buy_tp_offset=self.tp_multiple * self.std, sell_tp_offset=self.tp_multiple * self.std, buy_sl_offset=self.sl_multiple * self.std, sell_sl_offset=self.sl_multiple * self.std, min_open_time=None, max_open_time=None)

        self.last_dual_order_check_time = self.curr_time.timestamp()

        cur_equity = (self.quote_asset_balance + self.base_asset_balance * self.close)
        order_value = cur_equity * self.order_value_pct

        if do_place_order and order_value >= self.min_notional:

            if order_side == "BUY" and self.go_long:
                order_price = limit_buy_price


                order_size = order_value / order_price

                if available_quote_asset - order_value > 0:
                    order = self.place_order(order_type=order_type,
                                             order_side="BUY",
                                             price=order_price if order_type == 'LIMIT' else None,
                                             size=order_size,
                                             curr_time=self.curr_time
                                             )
                    self.open_trades[order.order_id] = {
                        'buy': order,
                        'sell': None,
                        'ts': self.curr_time.timestamp()
                    }

            elif order_side == "SELL" and self.go_short:
                order_price = limit_sell_price


                order_size = order_value / order_price

                if available_base_asset - order_size > 0:
                    order = self.place_order(order_type=order_type,
                                             order_side="SELL",
                                             price=order_price if order_type == 'LIMIT' else None,
                                             size=order_size,
                                             curr_time=self.curr_time
                                             )
                    self.open_trades[order.order_id] = {
                        'buy': None,
                        'sell': order,
                        'ts': self.curr_time.timestamp()
                    }

    def _is_place_order_condition_true(self):
        """
        Check place order condition
        """

        order_side = None
        place_order = False
        min_obv, max_obv = False, False

        if self.obv_diff is not None and len(self.obv_diff_list) > 1:

            if max(self.obv_diff_list[:-1]) < self.obv_diff:
                max_obv = True
            elif min(self.obv_diff_list[:-1]) > self.obv_diff:
                min_obv = True

        if ((self.use_obv and (self.ai_val == 1) and max_obv) or
                (not self.use_obv and (self.ai_val == 1) and self.rsi >= 100 - self.rsi_d)):
            order_side = "BUY"
            place_order = True
            return place_order, order_side

        elif ((self.use_obv and (self.ai_val == 2) and min_obv) or
              (not self.use_obv and (self.ai_val == 2) and self.rsi <= self.rsi_d)):
            order_side = "SELL"
            place_order = True

        return place_order, order_side

    # def __update_side(self):
    #     if self.obv_diff is not None and (not self.obv_diff_list or self.obv_diff_list[-1] != self.obv_diff):
    #         self.obv_diff_list.append(self.obv_diff)
    #         self.obv_diff_list = self.obv_diff_list[-self.ai_window_length // 2:]

    def update_indicators(self, candle: Candle):
        # self.ai_indicator.add(candle)
        self.std_indicator.add(candle.close)
        self.rsi_indicator.add(candle.close)
        self.obv_indicator.add(candle)

        if self.std_indicator.is_ready():
            self.std = self.std_indicator.result
        else:
            self.std = 0


        if self.rsi_indicator.is_ready():
            self.rsi = self.rsi_indicator.result
        else:
            self.rsi = 50

        if self.obv_indicator.is_ready():
            self.obv, self.obv_diff = self.obv_indicator.result
            self.ai_indicator.add([candle.close, abs(self.obv_diff)])
        else:
            self.ai_indicator.add([candle.close, (candle.buy_vol + candle.sell_vol)])

        if self.obv_diff is not None and (not self.obv_diff_list or self.obv_diff_list[-1] != self.obv_diff):
            self.obv_diff_list.append(self.obv_diff)
            self.obv_diff_list = self.obv_diff_list[-self.obv_window_length :]

        if self.ai_indicator.is_ready():
            if self.ai_indicator.result is None:
                self.ai_val = 0
            else:
                self.ai_val = torch.argmax(self.ai_indicator.result, dim=-1).item()  # 0 - NO Action, 1 - BUY, 2 - SELL
                # print(f"ai indicator: {self.ai_val}\n--------------------------")
        else:
            self.ai_val = 0
