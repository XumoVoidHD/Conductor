"""
HelloBars — minimal Nautilus strategy for learning.

What it does:
  - Subscribes to 1-minute bars on one instrument.
  - Logs each bar close.
  - Opens a small market BUY once (when flat after enough bars).
  - Closes the position a few bars later.

No alpha. Purpose is to see the Strategy lifecycle:
  on_start → on_bar → submit_order → on_order_filled → on_stop
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy


class HelloBarsConfig(StrategyConfig, frozen=True):
    """Configuration for ``HelloBars``."""

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal = Decimal("100_000")
    buy_after_bars: int = 3
    sell_after_bars: int = 8


class HelloBars(Strategy):
    """
    Logs bars and places one round-trip market order in a backtest.

    Parameters
    ----------
    config : HelloBarsConfig
        Strategy configuration.
    """

    def __init__(self, config: HelloBarsConfig) -> None:
        super().__init__(config)
        self._bar_count = 0
        self._instrument: Instrument | None = None

    def on_start(self) -> None:
        """Subscribe to bars once the engine has started us."""
        self._instrument = self.cache.instrument(self.config.instrument_id)
        if self._instrument is None:
            self.log.error(f"Instrument not in cache: {self.config.instrument_id}")
            self.stop()
            return

        self.subscribe_bars(self.config.bar_type)
        self.log.info(
            f"HelloBars started on {self.config.instrument_id} "
            f"(buy after {self.config.buy_after_bars} bars, "
            f"sell after {self.config.sell_after_bars})",
        )

    def on_bar(self, bar: Bar) -> None:
        """React to each bar."""
        self._bar_count += 1
        self.log.info(f"Bar #{self._bar_count} close={bar.close}")

        if self._instrument is None:
            return

        if (
            self._bar_count == self.config.buy_after_bars
            and self.portfolio.is_flat(self.config.instrument_id)
        ):
            qty = self._instrument.make_qty(self.config.trade_size)
            order = self.order_factory.market(
                instrument_id=self.config.instrument_id,
                order_side=OrderSide.BUY,
                quantity=qty,
                time_in_force=TimeInForce.GTC,
            )
            self.submit_order(order)
            self.log.info(f"Submitted BUY {qty}")

        elif (
            self._bar_count == self.config.sell_after_bars
            and not self.portfolio.is_flat(self.config.instrument_id)
        ):
            self.close_all_positions(self.config.instrument_id)
            self.log.info("Requested close all positions")

    def on_stop(self) -> None:
        """Clean up subscriptions when the engine stops us."""
        if self._instrument is not None:
            self.unsubscribe_bars(self.config.bar_type)
        self.log.info(f"HelloBars stopped after {self._bar_count} bars")
