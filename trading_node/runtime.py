"""Trading Node runtime — bootstrap-driven worker."""
from __future__ import annotations

import asyncio
import importlib
import os
import socket
import threading
from dataclasses import dataclass
from dataclasses import field

from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.trading.strategy import Strategy

from trading_node.bootstrap import TradingNodeBootstrap
from trading_node.bootstrap import load_bootstrap
from trading_node.brokers import build_broker

GRACEFUL_STRATEGY_STOP_TIMEOUT_SEC = 10.0
GRACEFUL_STRATEGY_POLL_SEC = 0.1
KNOWN_COMMANDS = "run, halt, status, reset, shutdown, kill"


@dataclass
class WorkerState:
    shutting_down: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


def _load_strategy(bootstrap: TradingNodeBootstrap) -> Strategy:
    spec = bootstrap.strategy
    if spec.module != "strategies.running_ping":
        raise ValueError(f"unsupported strategy module for v1: {spec.module}")

    module = importlib.import_module(spec.module)
    strategy_cls = getattr(module, spec.class_name)
    config_cls = getattr(module, spec.config_class)

    config = config_cls()
    return strategy_cls(config=config)


def _build_node(bootstrap: TradingNodeBootstrap) -> tuple[TradingNode, StrategyId]:
    broker_setup = build_broker(bootstrap.broker.adapter, bootstrap.broker.config)

    node_config = TradingNodeConfig(
        trader_id=TraderId(bootstrap.trader_id),
        logging=LoggingConfig(log_level="INFO"),
        data_clients=broker_setup.data_clients,
        exec_clients=broker_setup.exec_clients,
    )

    strategy = _load_strategy(bootstrap)
    node = TradingNode(config=node_config)
    node.trader.add_strategy(strategy)
    strategy_id = strategy.id

    broker_setup.register_factories(node)
    return node, strategy_id


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
    strategy = _get_strategy(node, strategy_id)
    if strategy is None:
        raise ValueError(f"Strategy {strategy_id} not found")
    if strategy.is_stopped:
        strategy.reset()
    strategy.start()


def _kill_node(node: TradingNode) -> None:
    print("KILL SWITCH: immediate node shutdown")
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

    if cmd in ("halt", "stop"):
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if not strategy.is_running:
            return "ERROR strategy already stopped"
        loop.call_soon_threadsafe(node.trader.stop_strategy, strategy_id)
        return "OK strategy stop requested"

    if cmd == "reset":
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if strategy.is_running:
            return "ERROR strategy is running; halt first"
        loop.call_soon_threadsafe(strategy.reset)
        return "OK strategy reset"

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
        return "OK graceful shutdown started"

    if cmd == "kill":
        with state.lock:
            state.shutting_down = True
        stop_event.set()
        loop.call_soon_threadsafe(_kill_node, node)
        return "OK kill switch activated"

    return f"ERROR unknown command '{cmd}' (use {KNOWN_COMMANDS})"


def _control_server(
    *,
    loop: asyncio.AbstractEventLoop,
    node: TradingNode,
    strategy_id: StrategyId,
    state: WorkerState,
    stop_event: threading.Event,
    host: str,
    port: int,
) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)
    server.settimeout(1.0)

    print(f"Control socket listening on {host}:{port}")

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


async def _run_node(
    node: TradingNode,
    strategy_id: StrategyId,
    bootstrap: TradingNodeBootstrap,
) -> None:
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
            "host": os.getenv("CONTROL_BIND_HOST", bootstrap.control_host),
            "port": bootstrap.control_port,
        },
        daemon=True,
    ).start()

    print(f"Trading node {bootstrap.node_id} ready. Strategy {strategy_id} is STOPPED.")

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


def run() -> None:
    bootstrap = load_bootstrap()
    node, strategy_id = _build_node(bootstrap)

    broker_cfg = bootstrap.broker.config
    print("=" * 60)
    print(f"Trading Node {bootstrap.node_id} (user={bootstrap.user_id})")
    print(f"Broker {bootstrap.broker.adapter} config_keys={sorted(broker_cfg.keys())}")
    print(f"Strategy {bootstrap.strategy.module}:{bootstrap.strategy.class_name}")
    print(f"Control {bootstrap.control_host}:{bootstrap.control_port}")
    print("=" * 60)

    node.build()
    loop = node.kernel.loop
    try:
        loop.run_until_complete(_run_node(node, strategy_id, bootstrap))
    except KeyboardInterrupt:
        if node.is_running():
            loop.run_until_complete(
                _graceful_shutdown(node, strategy_id, threading.Event()),
            )
