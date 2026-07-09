"""Bybit — Nautilus live adapters (testnet/mainnet/demo)."""
from __future__ import annotations

from typing import Any

from nautilus_trader.adapters.bybit import BYBIT
from nautilus_trader.adapters.bybit import BybitDataClientConfig
from nautilus_trader.adapters.bybit import BybitEnvironment
from nautilus_trader.adapters.bybit import BybitExecClientConfig
from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.bybit import BybitLiveExecClientFactory
from nautilus_trader.adapters.bybit import BybitProductType
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.model.identifiers import InstrumentId

from trading_node.brokers.types import BrokerSetup

_ENVIRONMENT_MAP = {
    "mainnet": BybitEnvironment.MAINNET,
    "testnet": BybitEnvironment.TESTNET,
    "demo": BybitEnvironment.DEMO,
}

_PRODUCT_TYPE_MAP = {
    "spot": BybitProductType.SPOT,
    "linear": BybitProductType.LINEAR,
    "inverse": BybitProductType.INVERSE,
    "option": BybitProductType.OPTION,
}


def _parse_environment(raw: Any) -> BybitEnvironment:
    if raw is None:
        raise ValueError("broker.config.environment is required for bybit")
    key = str(raw).strip().lower()
    env = _ENVIRONMENT_MAP.get(key)
    if env is None:
        supported = ", ".join(sorted(_ENVIRONMENT_MAP))
        raise ValueError(f"unsupported bybit environment '{raw}' (supported: {supported})")
    return env


def _parse_product_types(raw: Any) -> tuple[BybitProductType, ...]:
    if not raw:
        raise ValueError("broker.config.product_types is required for bybit")
    if not isinstance(raw, list):
        raise ValueError("broker.config.product_types must be a list")

    product_types: list[BybitProductType] = []
    for item in raw:
        key = str(item).strip().lower()
        product_type = _PRODUCT_TYPE_MAP.get(key)
        if product_type is None:
            supported = ", ".join(sorted(_PRODUCT_TYPE_MAP))
            raise ValueError(f"unsupported bybit product_type '{item}' (supported: {supported})")
        product_types.append(product_type)

    return tuple(product_types)


def _build_instrument_provider(config: dict[str, Any]) -> InstrumentProviderConfig:
    if config.get("load_all_instruments"):
        return InstrumentProviderConfig(load_all=True)

    instrument_ids = config.get("instrument_ids")
    if not instrument_ids:
        raise ValueError(
            "broker.config.instrument_ids is required for bybit "
            "(or set load_all_instruments=true)",
        )
    if not isinstance(instrument_ids, list):
        raise ValueError("broker.config.instrument_ids must be a list")

    return InstrumentProviderConfig(
        load_all=False,
        load_ids=frozenset(InstrumentId.from_str(str(item)) for item in instrument_ids),
    )


def build_bybit(config: dict[str, Any]) -> BrokerSetup:
    api_key = config.get("api_key")
    api_secret = config.get("api_secret")
    if not api_key:
        raise ValueError("broker.config.api_key is required for bybit")
    if not api_secret:
        raise ValueError("broker.config.api_secret is required for bybit")

    environment = _parse_environment(config.get("environment"))
    product_types = _parse_product_types(config.get("product_types"))
    instrument_provider = _build_instrument_provider(config)

    shared_kwargs = {
        "api_key": str(api_key),
        "api_secret": str(api_secret),
        "environment": environment,
        "product_types": product_types,
        "instrument_provider": instrument_provider,
    }

    exec_kwargs = dict(shared_kwargs)
    if product_types == (BybitProductType.SPOT,):
        exec_kwargs["use_spot_position_reports"] = bool(
            config.get("use_spot_position_reports", True),
        )

    return BrokerSetup(
        data_clients={BYBIT: BybitDataClientConfig(**shared_kwargs)},
        exec_clients={BYBIT: BybitExecClientConfig(**exec_kwargs)},
        data_factories={BYBIT: BybitLiveDataClientFactory},
        exec_factories={BYBIT: BybitLiveExecClientFactory},
    )
