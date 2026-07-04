"""
EmaCross — simple fast/slow EMA crossover for learning live data.

Long-only variant (good for paper stock accounts):
  - Fast EMA crosses above slow EMA → buy when flat
  - Fast EMA crosses below slow EMA → close any long

No alpha. Purpose is to see indicators + live bars from IBKR:
  on_start → request_bars (warmup) → subscribe_bars → on_bar → orders
"""
from __future__ import annotations

from decimal import Decimal

import pandas as pd

from nautilus_trader.config import PositiveInt
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.trading.strategy import Strategy


class EmaCrossConfig(StrategyConfig, frozen=True):
    """Configuration for ``EmaCross``."""

    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: PositiveInt = 10
    slow_ema_period: PositiveInt = 20
    request_historical_bars: bool = True
    close_positions_on_stop: bool = True


class EmaCross(Strategy):
    """Long-only EMA crossover on live or historical bars."""

    def __init__(self, config: EmaCrossConfig) -> None:
        PyCondition.is_true(
            config.fast_ema_period < config.slow_ema_period,
            "{config.fast_ema_period=} must be less than {config.slow_ema_period=}",
        )
        super().__init__(config)
        self._instrument: Instrument | None = None
        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)

    def on_start(self) -> None:
        self._instrument = self.cache.instrument(self.config.instrument_id)
        if self._instrument is None:
            self.log.error(f"Instrument not in cache: {self.config.instrument_id}")
            self.stop()
            return

        self.register_indicator_for_bars(self.config.bar_type, self.fast_ema)
        self.register_indicator_for_bars(self.config.bar_type, self.slow_ema)

        if self.config.request_historical_bars:
            self.request_bars(
                self.config.bar_type,
                start=self._clock.utc_now() - pd.Timedelta(days=1),
            )

        self.subscribe_bars(self.config.bar_type)
        self.log.info(
            f"EmaCross started on {self.config.instrument_id} "
            f"(fast={self.config.fast_ema_period}, slow={self.config.slow_ema_period})",
        )

    def on_bar(self, bar: Bar) -> None:
        if not self.indicators_initialized():
            self.log.info(
                f"Warming up EMAs "
                f"[{self.cache.bar_count(self.config.bar_type)} bars received]",
            )
            return

        if bar.is_single_price():
            return

        fast = self.fast_ema.value
        slow = self.slow_ema.value
        self.log.info(
            f"Bar close={bar.close} fast_ema={fast:.5f} slow_ema={slow:.5f}",
        )

        if fast >= slow:
            if self.portfolio.is_flat(self.config.instrument_id):
                self._submit_market_order(OrderSide.BUY)
        elif not self.portfolio.is_flat(self.config.instrument_id):
            self.close_all_positions(self.config.instrument_id)
            self.log.info("Fast EMA below slow — closed long")

    def on_order_filled(self, event: OrderFilled) -> None:
        self.log.info(f"Fill: {event.order_side} {event.last_qty} @ {event.last_px}")

    def on_stop(self) -> None:
        self.unsubscribe_bars(self.config.bar_type)
        if self.config.close_positions_on_stop:
            self.close_all_positions(self.config.instrument_id)
        self.log.info("EmaCross stopped")

    def _submit_market_order(self, side: OrderSide) -> None:
        if self._instrument is None:
            return

        qty = self._instrument.make_qty(self.config.trade_size)
        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=qty,
            time_in_force=TimeInForce.GTC,
        )
        self.submit_order(order)
        self.log.info(f"Submitted {side.name} {qty}")
