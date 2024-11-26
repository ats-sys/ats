from ats.state.simple_state import SimpleState
from ats.exchanges.data_classes.candle import Candle
from ats.strategies.advanced_base_strategy import AdvancedBaseStrategy
from ats.exceptions.general_exceptions import ConfigValidationException


class Strategy(AdvancedBaseStrategy):
    """
    This strategy is just a test strategy that does not place any orders.
    The sole purpose of this is to verify the basic operations.
    """

    def __init__(self, config, state: SimpleState = None):
        super().__init__(config, state)
        self.base_symbol, self.quote_symbol = self.config['base_symbol'], self.config['quote_symbol']

    def validate_config(self) -> None:
        required_properties = ['base_symbol', 'quote_symbol']

        for prop in required_properties:
            if prop not in self.config:
                raise ConfigValidationException('Exchange Config', f"Missing property '{prop}' in config.")

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

        usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity = self._get_equity_balance()
        self.register_plot_data(self.curr_time, usable_base_asset, usable_quote_asset, total_base_asset, total_quote_asset, usable_equity, total_equity)

        self.order_states.update()
        self.check_execution(candle)
        self.plot_profit_components(self.curr_time)
