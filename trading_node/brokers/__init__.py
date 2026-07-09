"""Broker adapter registry for trading nodes."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trading_node.brokers.types import BrokerSetup

DEFAULT_BROKER_ADAPTER = "bybit"

SUPPORTED_BROKER_ADAPTERS = frozenset({"bybit", "interactive_brokers"})

BrokerBuilder = Callable[[dict[str, Any]], BrokerSetup]


def _load_builder(adapter: str) -> BrokerBuilder:
    if adapter == "bybit":
        from trading_node.brokers.bybit import build_bybit

        return build_bybit
    if adapter == "interactive_brokers":
        from trading_node.brokers.interactive_brokers import build_interactive_brokers

        return build_interactive_brokers
    supported = ", ".join(sorted(SUPPORTED_BROKER_ADAPTERS))
    raise ValueError(f"unsupported broker adapter '{adapter}' (supported: {supported})")


def build_broker(adapter: str, config: dict[str, Any]) -> BrokerSetup:
    builder = _load_builder(adapter)
    return builder(config)
