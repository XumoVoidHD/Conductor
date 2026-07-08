"""Interactive Brokers (TWS / Gateway) — Nautilus default live adapters."""
from __future__ import annotations

from typing import Any

from nautilus_trader.adapters.interactive_brokers.common import IB_CLIENT_ID
from nautilus_trader.adapters.interactive_brokers.common import IBContract
from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersDataClientConfig,
)
from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersExecClientConfig,
)
from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersInstrumentProviderConfig,
)
from nautilus_trader.adapters.interactive_brokers.factories import (
    InteractiveBrokersLiveDataClientFactory,
)
from nautilus_trader.adapters.interactive_brokers.factories import (
    InteractiveBrokersLiveExecClientFactory,
)

from trading_node.brokers.types import BrokerSetup


def _parse_contracts(raw: list[dict[str, Any]] | None) -> frozenset[IBContract]:
    if not raw:
        raise ValueError("broker.config.load_contracts is required")
    return frozenset(
        IBContract(
            secType=str(c["secType"]),
            symbol=str(c["symbol"]),
            exchange=str(c["exchange"]),
            currency=str(c["currency"]),
        )
        for c in raw
    )


def build_interactive_brokers(config: dict[str, Any]) -> BrokerSetup:
    account_id = config.get("account_id")
    if not account_id:
        raise ValueError("broker.config.account_id is required for interactive_brokers")

    ibg_client_id = config.get("ibg_client_id")
    if ibg_client_id is None:
        raise ValueError("broker.config.ibg_client_id is required for interactive_brokers")

    ibg_host = config.get("ibg_host")
    ibg_port = config.get("ibg_port")
    if not ibg_host:
        raise ValueError("broker.config.ibg_host is required for interactive_brokers")
    if ibg_port is None:
        raise ValueError("broker.config.ibg_port is required for interactive_brokers")

    instrument_provider = InteractiveBrokersInstrumentProviderConfig(
        load_contracts=_parse_contracts(config.get("load_contracts")),
    )
    shared_ib_kwargs = {
        "ibg_host": str(ibg_host),
        "ibg_port": int(ibg_port),
        "ibg_client_id": int(ibg_client_id),
        "instrument_provider": instrument_provider,
    }

    client_id = IB_CLIENT_ID.value
    return BrokerSetup(
        data_clients={
            client_id: InteractiveBrokersDataClientConfig(
                **shared_ib_kwargs,
                use_regular_trading_hours=bool(config.get("use_regular_trading_hours", True)),
            ),
        },
        exec_clients={
            client_id: InteractiveBrokersExecClientConfig(
                **shared_ib_kwargs,
                account_id=str(account_id),
            ),
        },
        data_factories={client_id: InteractiveBrokersLiveDataClientFactory},
        exec_factories={client_id: InteractiveBrokersLiveExecClientFactory},
    )
