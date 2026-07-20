"""Catalog of strategies the dashboard can deploy."""
from __future__ import annotations

from typing import Any


# Default Bybit linear instrument — override via deploy request if needed.
_BYBIT_LINEAR = "BTCUSDT-LINEAR.BYBIT"
_BYBIT_BAR = "BTCUSDT-LINEAR.BYBIT-1-MINUTE-LAST-EXTERNAL"

STRATEGY_CATALOG: list[dict[str, Any]] = [
    {
        "id": "running_ping",
        "name": "RunningPing",
        "description": "Smoke test — prints 'running' every 10s. No orders.",
        "module": "strategies.running_ping",
        "class_name": "RunningPing",
        "config_class": "RunningPingConfig",
        "default_config": {},
        "requires_market_data": False,
    },
    {
        "id": "hello_bars",
        "name": "HelloBars",
        "description": "Logs bars and places one small buy/sell round-trip.",
        "module": "strategies.hello_bars",
        "class_name": "HelloBars",
        "config_class": "HelloBarsConfig",
        "default_config": {
            "instrument_id": _BYBIT_LINEAR,
            "bar_type": _BYBIT_BAR,
            "trade_size": "0.001",
            "buy_after_bars": 3,
            "sell_after_bars": 8,
        },
        "requires_market_data": True,
    },
    {
        "id": "ema_cross",
        "name": "EmaCross",
        "description": "Long-only fast/slow EMA crossover on 1-minute bars.",
        "module": "strategies.ema_cross",
        "class_name": "EmaCross",
        "config_class": "EmaCrossConfig",
        "default_config": {
            "instrument_id": _BYBIT_LINEAR,
            "bar_type": _BYBIT_BAR,
            "trade_size": "0.001",
            "fast_ema_period": 10,
            "slow_ema_period": 20,
            "request_historical_bars": True,
            "close_positions_on_stop": True,
        },
        "requires_market_data": True,
    },
]


def list_strategies() -> list[dict[str, Any]]:
    return list(STRATEGY_CATALOG)


def get_strategy(strategy_id: str) -> dict[str, Any] | None:
    for item in STRATEGY_CATALOG:
        if item["id"] == strategy_id:
            return item
    return None
