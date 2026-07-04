#!/usr/bin/env python3
"""
Run the HelloBars strategy in a minimal Nautilus backtest.

This is Step 1 of Conductor: understand what Nautilus gives you inside one process
before adding Docker, Redis, or a control plane.

Usage (from Conductor repo root, after installing nautilus-trader):

    python -m learn.run_backtest
"""
from __future__ import annotations

from decimal import Decimal

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

from learn.synthetic_data import make_bar_type
from learn.synthetic_data import make_eurusd_instrument
from learn.synthetic_data import make_rising_bars
from strategies.hello_bars import HelloBars
from strategies.hello_bars import HelloBarsConfig


def main() -> None:
    instrument = make_eurusd_instrument()
    bar_type = make_bar_type(instrument.id)
    bars = make_rising_bars(bar_type, instrument, count=20)

    engine_config = BacktestEngineConfig(
        trader_id=TraderId("CONDUCTOR-LEARN-001"),
        logging=LoggingConfig(log_level="INFO"),
    )
    engine = BacktestEngine(config=engine_config)

    # Simulated exchange + funded account
    engine.add_venue(
        venue=Venue("SIM"),
        oms_type=OmsType.HEDGING,
        account_type=AccountType.MARGIN,
        base_currency=USD,
        starting_balances=[Money(1_000_000, USD)],
    )
    engine.add_instrument(instrument)
    engine.add_data(bars)

    strategy_config = HelloBarsConfig(
        instrument_id=instrument.id,
        bar_type=bar_type,
        trade_size=Decimal("100_000"),
        buy_after_bars=3,
        sell_after_bars=8,
    )
    strategy = HelloBars(config=strategy_config)
    engine.add_strategy(strategy)

    print("=" * 60)
    print("Starting backtest — watch logs for bar / order events")
    print("=" * 60)

    engine.run()

    print("=" * 60)
    print("Backtest finished")
    print("=" * 60)

    engine.dispose()


if __name__ == "__main__":
    main()
