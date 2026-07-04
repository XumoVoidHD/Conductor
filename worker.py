#!/usr/bin/env python3
"""
Trading worker — keeps IBKR + TradingNode running and waits for remote commands.

Start this first (leave it running):

    python worker.py

From another terminal, use control.py:

    python control.py run        # start strategy (rejected if already running)
    python control.py stop       # stop strategy (rejected if already stopped)
    python control.py status     # running / stopped / shutting_down
    python control.py shutdown   # graceful: stop strategy, then stop node
    python control.py kill       # emergency: stop node immediately
"""
from __future__ import annotations

import asyncio
import os
import socket
import threading
from dataclasses import dataclass
from dataclasses import field
from decimal import Decimal

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
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.trading.strategy import Strategy

from learn.run_ibkr_live import _load_env_file
from learn.run_ibkr_live import resolve_ib_endpoint
from strategies.ema_cross import EmaCross
from strategies.ema_cross import EmaCrossConfig

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
GRACEFUL_STRATEGY_STOP_TIMEOUT_SEC = 10.0
GRACEFUL_STRATEGY_POLL_SEC = 0.1

KNOWN_COMMANDS = "run, stop, status, shutdown, kill"


@dataclass
class WorkerState:
    """Shared control-plane state (socket thread + event loop)."""

    shutting_down: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


def _control_endpoint() -> tuple[str, int]:
    host = os.getenv("CONTROL_HOST", "127.0.0.1")
    port = int(os.getenv("CONTROL_PORT", "8765"))
    return host, port


def _get_strategy(node: TradingNode, strategy_id: StrategyId) -> Strategy | None:
    for strategy in node.trader.strategies():
        if strategy.id == strategy_id:
            return strategy
    return None


def _strategy_label(node: TradingNode, strategy_id: StrategyId) -> str:
    strategy = _get_strategy(node, strategy_id)
    if strategy is None:
        return "missing"
    if strategy.is_running:
        return "running"
    return "stopped"


def _start_strategy(node: TradingNode, strategy_id: StrategyId) -> None:
    """Start or restart after stop (STOPPED cannot go directly to START)."""
    strategy = _get_strategy(node, strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy {strategy_id} not found")
    if strategy.is_stopped:
        strategy.reset()
    strategy.start()


def _kill_node(node: TradingNode) -> None:
    print("KILL SWITCH: immediate node shutdown (strategy cleanup skipped)")
    node.stop()


async def _graceful_shutdown(
    node: TradingNode,
    strategy_id: StrategyId,
    stop_event: threading.Event,
) -> None:
    strategy = _get_strategy(node, strategy_id)

    if strategy is not None and strategy.is_running:
        print("Graceful shutdown: stopping strategy...")
        node.trader.stop_strategy(strategy_id)

        elapsed = 0.0
        while strategy.is_running and elapsed < GRACEFUL_STRATEGY_STOP_TIMEOUT_SEC:
            await asyncio.sleep(GRACEFUL_STRATEGY_POLL_SEC)
            elapsed += GRACEFUL_STRATEGY_POLL_SEC

        if strategy.is_running:
            print(
                "Graceful shutdown: strategy still running after "
                f"{GRACEFUL_STRATEGY_STOP_TIMEOUT_SEC:.0f}s — stopping node anyway",
            )
        else:
            print("Graceful shutdown: strategy stopped")
    else:
        print("Graceful shutdown: strategy already stopped")

    print("Graceful shutdown: stopping node...")
    stop_event.set()
    node.stop()


def _reject_if_shutting_down(state: WorkerState, cmd: str) -> str | None:
    if cmd in ("status", "kill"):
        return None
    with state.lock:
        if state.shutting_down:
            return "ERROR worker is shutting down"
    return None


def _handle_command(
    cmd: str,
    *,
    loop: asyncio.AbstractEventLoop,
    node: TradingNode,
    strategy_id: StrategyId,
    state: WorkerState,
    stop_event: threading.Event,
) -> str:
    if reject := _reject_if_shutting_down(state, cmd):
        return reject

    if cmd == "run":
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if strategy.is_running:
            return "ERROR strategy already running"
        loop.call_soon_threadsafe(_start_strategy, node, strategy_id)
        return "OK strategy start requested"

    if cmd == "stop":
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if not strategy.is_running:
            return "ERROR strategy already stopped"
        loop.call_soon_threadsafe(node.trader.stop_strategy, strategy_id)
        return "OK strategy stop requested"

    if cmd == "status":
        with state.lock:
            if state.shutting_down:
                return "OK worker=shutting_down"
        return f"OK strategy={_strategy_label(node, strategy_id)}"

    if cmd == "shutdown":
        with state.lock:
            if state.shutting_down:
                return "ERROR shutdown already in progress"
            state.shutting_down = True

        asyncio.run_coroutine_threadsafe(
            _graceful_shutdown(node, strategy_id, stop_event),
            loop,
        )
        return "OK graceful shutdown started (strategy stop, then node stop)"

    if cmd == "kill":
        with state.lock:
            state.shutting_down = True
        stop_event.set()
        loop.call_soon_threadsafe(_kill_node, node)
        return "OK kill switch activated — node stopping immediately"

    return f"ERROR unknown command '{cmd}' (use {KNOWN_COMMANDS})"


def _control_server(
    *,
    loop: asyncio.AbstractEventLoop,
    node: TradingNode,
    strategy_id: StrategyId,
    state: WorkerState,
    stop_event: threading.Event,
) -> None:
    host, port = _control_endpoint()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    server.settimeout(1.0)

    print(f"Control socket listening on {host}:{port}")
    print(f"Commands: python control.py {KNOWN_COMMANDS.replace(', ', '|')}")

    while not stop_event.is_set():
        try:
            conn, _addr = server.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        with conn:
            try:
                data = conn.recv(1024)
                cmd = data.decode("utf-8").strip().lower()
                reply = _handle_command(
                    cmd,
                    loop=loop,
                    node=node,
                    strategy_id=strategy_id,
                    state=state,
                    stop_event=stop_event,
                )
            except Exception as exc:
                reply = f"ERROR {exc}"
            conn.sendall(f"{reply}\n".encode("utf-8"))

    server.close()


async def _run_node(node: TradingNode, strategy_id: StrategyId) -> None:
    await node.kernel.start_async()
    node.trader.stop_strategy(strategy_id)

    loop = node.kernel.loop
    if loop is None:
        raise RuntimeError("No event loop on TradingNode")

    state = WorkerState()
    stop_event = threading.Event()
    threading.Thread(
        target=_control_server,
        kwargs={
            "loop": loop,
            "node": node,
            "strategy_id": strategy_id,
            "state": state,
            "stop_event": stop_event,
        },
        daemon=True,
    ).start()

    print(f"Node connected. Strategy {strategy_id} is STOPPED.")
    print("Send 'run' from control.py to start trading.")

    try:
        tasks: list[asyncio.Task] = [
            node.kernel.data_engine.get_cmd_queue_task(),
            node.kernel.data_engine.get_req_queue_task(),
            node.kernel.data_engine.get_res_queue_task(),
            node.kernel.data_engine.get_data_queue_task(),
            node.kernel.risk_engine.get_cmd_queue_task(),
            node.kernel.risk_engine.get_evt_queue_task(),
            node.kernel.exec_engine.get_cmd_queue_task(),
            node.kernel.exec_engine.get_evt_queue_task(),
        ]
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()


def main() -> None:
    _load_env_file()

    account_id = os.getenv("TWS_ACCOUNT")
    if not account_id:
        raise SystemExit("Set TWS_ACCOUNT in .env")

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
        trader_id=TraderId("CONDUCTOR-WORKER-001"),
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

    strategy = EmaCross(
        config=EmaCrossConfig(
            instrument_id=INSTRUMENT_ID,
            bar_type=bar_type,
            trade_size=TRADE_SIZE,
            fast_ema_period=FAST_EMA,
            slow_ema_period=SLOW_EMA,
        ),
    )

    node = TradingNode(config=node_config)
    node.trader.add_strategy(strategy)
    strategy_id = strategy.id

    node.add_data_client_factory(
        IB_CLIENT_ID.value,
        InteractiveBrokersLiveDataClientFactory,
    )
    node.add_exec_client_factory(
        IB_CLIENT_ID.value,
        InteractiveBrokersLiveExecClientFactory,
    )

    control_host, control_port = _control_endpoint()
    print("=" * 60)
    print(f"IBKR {ib_host}:{ib_port}  account={account_id}")
    print(f"Strategy {strategy_id}")
    print(f"Control {control_host}:{control_port}")
    print("=" * 60)

    node.build()

    loop = node.kernel.loop
    try:
        loop.run_until_complete(_run_node(node, strategy_id))
    except KeyboardInterrupt:
        print("\nKeyboard interrupt — graceful shutdown...")
        if node.is_running():
            loop.run_until_complete(
                _graceful_shutdown(node, strategy_id, threading.Event()),
            )


if __name__ == "__main__":
    main()
