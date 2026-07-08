"""Broker adapter registry for trading nodes."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from trading_node.brokers.interactive_brokers import build_interactive_brokers
from trading_node.brokers.types import BrokerSetup

DEFAULT_BROKER_ADAPTER = "interactive_brokers"

BrokerBuilder = Callable[[dict[str, Any]], BrokerSetup]

BROKER_BUILDERS: dict[str, BrokerBuilder] = {
    "interactive_brokers": build_interactive_brokers,
}


def build_broker(adapter: str, config: dict[str, Any]) -> BrokerSetup:
    builder = BROKER_BUILDERS.get(adapter)
    if builder is None:
        supported = ", ".join(sorted(BROKER_BUILDERS))
        raise ValueError(f"unsupported broker adapter '{adapter}' (supported: {supported})")
    return builder(config)
