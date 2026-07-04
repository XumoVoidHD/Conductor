"""
Synthetic FX instrument + bars for local backtests.

No catalog or CSV files required — enough to exercise a strategy end-to-end.
"""
from __future__ import annotations

from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarSpecification
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AggregationSource
from nautilus_trader.model.enums import BarAggregation
from nautilus_trader.model.enums import PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.test_kit.providers import TestInstrumentProvider


def make_eurusd_instrument() -> CurrencyPair:
    """Standard test EUR/USD pair (venue SIM)."""
    return TestInstrumentProvider.default_fx_ccy("EUR/USD")


def make_bar_type(instrument_id: InstrumentId) -> BarType:
    """1-minute EXTERNAL bars — matches data we inject into the backtest engine."""
    return BarType(
        instrument_id=instrument_id,
        bar_spec=BarSpecification(
            step=1,
            aggregation=BarAggregation.MINUTE,
            price_type=PriceType.BID,
        ),
        aggregation_source=AggregationSource.EXTERNAL,
    )


def make_rising_bars(
    bar_type: BarType,
    instrument: CurrencyPair,
    *,
    count: int = 20,
    start_price: float = 1.10000,
    step: float = 0.00010,
    volume: float = 1_000_000.0,
) -> list[Bar]:
    """
    Build ``count`` ascending 1-minute bars.

    Timestamps are synthetic nanosecond values spaced one minute apart.
    """
    bars: list[Bar] = []
    minute_ns = 60_000_000_000
    base_ts = 1_700_000_000_000_000_000  # arbitrary epoch-ish anchor

    for i in range(count):
        mid = start_price + i * step
        open_p = mid - step / 2
        close_p = mid + step / 2
        high_p = close_p + step / 4
        low_p = open_p - step / 4
        ts = base_ts + i * minute_ns

        bars.append(
            Bar(
                bar_type=bar_type,
                open=Price.from_str(f"{open_p:.5f}"),
                high=Price.from_str(f"{high_p:.5f}"),
                low=Price.from_str(f"{low_p:.5f}"),
                close=Price.from_str(f"{close_p:.5f}"),
                volume=Quantity.from_int(int(volume)),
                ts_event=ts,
                ts_init=ts,
            ),
        )

    return bars
