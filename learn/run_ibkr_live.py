#!/usr/bin/env python3
"""
Run EmaCross against live IBKR data via TWS / IB Gateway.

Step 2 of Conductor: one TradingNode process connected to TWS before adding
Redis, Docker, or the control plane.

Prerequisites:
  - TWS or IB Gateway running with API enabled (Configure → API → Settings)
  - Paper account recommended
  - Market data subscription for the symbol (or use delayed data — see below)

Usage (from Conductor repo root):

    python -m learn.run_ibkr_live

Loads ``.env`` from the repo root (see ``.env.example``).
Environment variables override ``.env`` if already set in the shell.
"""
from __future__ import annotations

import os
import socket
from decimal import Decimal
from pathlib import Path

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
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TraderId

from strategies.ema_cross import EmaCross
from strategies.ema_cross import EmaCrossConfig

# --- edit these to taste ---------------------------------------------------
# IB simplified symbology: AAPL.NASDAQ, EUR/USD.IDEALPRO, etc.
INSTRUMENT_ID = InstrumentId.from_str("AAPL.NASDAQ")
IB_CONTRACT = IBContract(
    secType="STK",
    symbol="AAPL",
    exchange="SMART",
    currency="USD",
)
BAR_SPEC = "1-MINUTE-LAST-EXTERNAL"
TRADE_SIZE = Decimal("1")
FAST_EMA = 10
SLOW_EMA = 20
# ---------------------------------------------------------------------------

LOCALHOSTS = frozenset({"127.0.0.1", "localhost"})
DEFAULT_IB_PORT_CANDIDATES = (7497, 4002, 7496, 4001)
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_env_file() -> None:
    """Load repo-root ``.env`` into os.environ (does not override existing vars)."""
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _is_ib_endpoint_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_ib_endpoint() -> tuple[str, int]:
    host = os.getenv("IB_HOST", "127.0.0.1")
    port_value = os.getenv("IB_PORT")
    if port_value is not None:
        return host, int(port_value)

    if host not in LOCALHOSTS:
        return host, 7497

    for port in DEFAULT_IB_PORT_CANDIDATES:
        if _is_ib_endpoint_reachable(host, port):
            return host, port

    return host, 7497


def main() -> None:
    _load_env_file()

    account_id = os.getenv("TWS_ACCOUNT")
    if not account_id:
        raise SystemExit(
            "Set TWS_ACCOUNT in .env or the environment (e.g. DU1234567 for paper).",
        )

    ib_host, ib_port = resolve_ib_endpoint()
    ib_client_id = int(os.getenv("IB_CLIENT_ID", "10"))
    bar_type = BarType.from_str(f"{INSTRUMENT_ID}-{BAR_SPEC}")

    instrument_provider = InteractiveBrokersInstrumentProviderConfig(
        load_contracts=frozenset({IB_CONTRACT}),
    )
    shared_ib_kwargs = {
        "ibg_host": ib_host,
        "ibg_port": ib_port,
        "ibg_client_id": ib_client_id,
        "instrument_provider": instrument_provider,
    }

    node_config = TradingNodeConfig(
        trader_id=TraderId("CONDUCTOR-LEARN-002"),
        logging=LoggingConfig(log_level="INFO"),
        data_clients={
            IB_CLIENT_ID.value: InteractiveBrokersDataClientConfig(
                **shared_ib_kwargs,
                use_regular_trading_hours=True,
            ),
        },
        exec_clients={
            IB_CLIENT_ID.value: InteractiveBrokersExecClientConfig(
                **shared_ib_kwargs,
                account_id=account_id,
            ),
        },
    )

    strategy_config = EmaCrossConfig(
        instrument_id=INSTRUMENT_ID,
        bar_type=bar_type,
        trade_size=TRADE_SIZE,
        fast_ema_period=FAST_EMA,
        slow_ema_period=SLOW_EMA,
    )

    node = TradingNode(config=node_config)
    node.trader.add_strategy(EmaCross(config=strategy_config))
    node.add_data_client_factory(
        IB_CLIENT_ID.value,
        InteractiveBrokersLiveDataClientFactory,
    )
    node.add_exec_client_factory(
        IB_CLIENT_ID.value,
        InteractiveBrokersLiveExecClientFactory,
    )

    print("=" * 60)
    print(f"Connecting to IBKR at {ib_host}:{ib_port} (client_id={ib_client_id})")
    print(f"Instrument: {INSTRUMENT_ID}  bars: {bar_type}")
    print(f"Account: {account_id}  trade_size={TRADE_SIZE}")
    print("Ctrl+C to stop")
    print("=" * 60)

    node.build()

    try:
        node.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        node.stop()


if __name__ == "__main__":
    main()
