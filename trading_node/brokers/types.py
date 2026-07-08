"""Broker builder types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from nautilus_trader.live.node import TradingNode


@dataclass
class BrokerSetup:
    data_clients: dict[str, Any]
    exec_clients: dict[str, Any]
    data_factories: dict[str, Any]
    exec_factories: dict[str, Any]

    def register_factories(self, node: TradingNode) -> None:
        for client_id, factory in self.data_factories.items():
            node.add_data_client_factory(client_id, factory)
        for client_id, factory in self.exec_factories.items():
            node.add_exec_client_factory(client_id, factory)
