"""Trading Node runtime — bootstrap-driven worker."""
from __future__ import annotations

import asyncio
import importlib
import logging
import os
import socket
import sys
import threading
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import TextIO

from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.trading.strategy import Strategy

from trading_node.bootstrap import TradingNodeBootstrap
from trading_node.bootstrap import load_bootstrap
from trading_node.brokers import build_broker
from trading_node.observe import LogPublisher
from trading_node.observe import RedisLogHandler
from trading_node.observe import build_log_publisher

GRACEFUL_STRATEGY_STOP_TIMEOUT_SEC = 10.0
GRACEFUL_STRATEGY_POLL_SEC = 0.1
KNOWN_COMMANDS = "run, halt, status, reset, shutdown, kill, snapshot, summary"
RECENT_LOG_LIMIT = 200


@dataclass
class WorkerState:
    shutting_down: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)
    recent_logs: list[str] = field(default_factory=list)
    recent_errors: list[str] = field(default_factory=list)
    node_id: str = ""
    user_id: str = ""
    log_publisher: LogPublisher | None = None

    def push_log(self, message: str) -> None:
        with self.lock:
            self.recent_logs.append(message)
            if len(self.recent_logs) > RECENT_LOG_LIMIT:
                self.recent_logs = self.recent_logs[-RECENT_LOG_LIMIT:]
        if self.log_publisher is not None:
            self.log_publisher.publish_log(message, level="INFO")

    def push_error(self, message: str) -> None:
        with self.lock:
            self.recent_errors.append(message)
            if len(self.recent_errors) > RECENT_LOG_LIMIT:
                self.recent_errors = self.recent_errors[-RECENT_LOG_LIMIT:]
        if self.log_publisher is not None:
            self.log_publisher.publish_log(message, level="ERROR")


class _StreamTee(TextIO):
    """Mirror stdout/stderr lines to the observe log publisher."""

    def __init__(self, original: TextIO, publisher: LogPublisher, *, level: str) -> None:
        self._original = original
        self._publisher = publisher
        self._level = level
        self._buffer = ""

    def write(self, data: str) -> int:
        written = self._original.write(data)
        if not data:
            return written
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            stripped = line.strip()
            if stripped:
                self._publisher.publish_log(stripped, level=self._level)
        return written

    def flush(self) -> None:
        self._original.flush()
        if self._buffer.strip():
            self._publisher.publish_log(self._buffer.strip(), level=self._level)
            self._buffer = ""

    def isatty(self) -> bool:
        return self._original.isatty()


def _install_observe_logging(bootstrap: TradingNodeBootstrap) -> LogPublisher | None:
    publisher = build_log_publisher(
        user_id=bootstrap.user_id,
        node_id=bootstrap.node_id,
    )
    if publisher is None:
        return None

    handler = RedisLogHandler(publisher)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"),
    )
    for logger_name in ("", "nautilus_trader", "trading_node"):
        logging.getLogger(logger_name).addHandler(handler)

    sys.stdout = _StreamTee(sys.stdout, publisher, level="INFO")  # type: ignore[assignment]
    sys.stderr = _StreamTee(sys.stderr, publisher, level="ERROR")  # type: ignore[assignment]
    return publisher


def _coerce_strategy_config_value(key: str, value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if key == "instrument_id":
        from nautilus_trader.model.identifiers import InstrumentId

        return InstrumentId.from_str(value)
    if key == "bar_type":
        from nautilus_trader.model.data import BarType

        return BarType.from_str(value)
    if key == "trade_size":
        from decimal import Decimal

        return Decimal(value)
    return value


def _build_strategy_config(config_cls: type, raw: dict[str, Any]) -> Any:
    if not raw:
        return config_cls()
    kwargs = {key: _coerce_strategy_config_value(key, value) for key, value in raw.items()}
    return config_cls(**kwargs)


def _load_strategy(bootstrap: TradingNodeBootstrap) -> Strategy:
    spec = bootstrap.strategy
    if not spec.module.startswith("strategies."):
        raise ValueError(
            f"unsupported strategy module '{spec.module}' "
            "(must be under strategies.*)",
        )

    if spec.artifact_dir:
        artifact_root = spec.artifact_dir
        if artifact_root not in sys.path:
            sys.path.insert(0, artifact_root)

    module = importlib.import_module(spec.module)
    strategy_cls = getattr(module, spec.class_name)
    config_cls = getattr(module, spec.config_class)

    config = _build_strategy_config(config_cls, dict(spec.config))
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
    if cmd in ("status", "kill", "snapshot", "summary"):
        return None
    with state.lock:
        if state.shutting_down:
            return "ERROR worker is shutting down"
    return None


def _run_snapshot_on_loop(
    *,
    loop: asyncio.AbstractEventLoop,
    node: TradingNode,
    strategy_id: StrategyId,
    state: WorkerState,
) -> dict[str, Any]:
    import concurrent.futures

    from trading_node.snapshot import build_node_snapshot

    future: concurrent.futures.Future[dict[str, Any]] = concurrent.futures.Future()

    def _build() -> None:
        try:
            with state.lock:
                logs = list(state.recent_logs)
                errors = list(state.recent_errors)
                shutting_down = state.shutting_down
                node_id = state.node_id
                user_id = state.user_id
            future.set_result(
                build_node_snapshot(
                    node,
                    strategy_id=strategy_id,
                    node_id=node_id,
                    user_id=user_id,
                    recent_logs=logs,
                    recent_errors=errors,
                    shutting_down=shutting_down,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            future.set_exception(exc)

    loop.call_soon_threadsafe(_build)
    return future.result(timeout=15.0)


def _run_summary_on_loop(
    *,
    loop: asyncio.AbstractEventLoop,
    node: TradingNode,
    strategy_id: StrategyId,
    state: WorkerState,
) -> dict[str, Any]:
    import concurrent.futures

    from trading_node.snapshot import build_node_summary

    future: concurrent.futures.Future[dict[str, Any]] = concurrent.futures.Future()

    def _build() -> None:
        try:
            with state.lock:
                shutting_down = state.shutting_down
                node_id = state.node_id
                user_id = state.user_id
            future.set_result(
                build_node_summary(
                    node,
                    strategy_id=strategy_id,
                    node_id=node_id,
                    user_id=user_id,
                    shutting_down=shutting_down,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            future.set_exception(exc)

    loop.call_soon_threadsafe(_build)
    return future.result(timeout=10.0)


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
        state.push_log("command=run accepted")
        return "OK strategy start requested"

    if cmd in ("halt", "stop"):
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if not strategy.is_running:
            return "ERROR strategy already stopped"
        loop.call_soon_threadsafe(node.trader.stop_strategy, strategy_id)
        state.push_log("command=halt accepted")
        return "OK strategy stop requested"

    if cmd == "reset":
        strategy = _get_strategy(node, strategy_id)
        if strategy is None:
            return "ERROR strategy not found"
        if strategy.is_running:
            return "ERROR strategy is running; halt first"
        loop.call_soon_threadsafe(strategy.reset)
        state.push_log("command=reset accepted")
        return "OK strategy reset"

    if cmd == "status":
        with state.lock:
            if state.shutting_down:
                return "OK worker=shutting_down"
        return f"OK strategy={_strategy_label(node, strategy_id)}"

    if cmd == "snapshot":
        import json

        try:
            payload = _run_snapshot_on_loop(
                loop=loop,
                node=node,
                strategy_id=strategy_id,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            state.push_error(f"snapshot failed: {exc}")
            return f"ERROR snapshot failed: {exc}"
        # Compact single-line JSON after OK marker for TCP protocol.
        return "OK SNAPSHOT " + json.dumps(payload, separators=(",", ":"), default=str)

    if cmd == "summary":
        import json

        try:
            payload = _run_summary_on_loop(
                loop=loop,
                node=node,
                strategy_id=strategy_id,
                state=state,
            )
        except Exception as exc:  # noqa: BLE001
            state.push_error(f"summary failed: {exc}")
            return f"ERROR summary failed: {exc}"
        return "OK SUMMARY " + json.dumps(payload, separators=(",", ":"), default=str)

    if cmd == "shutdown":
        with state.lock:
            if state.shutting_down:
                return "ERROR shutdown already in progress"
            state.shutting_down = True
        state.push_log("command=shutdown accepted")
        asyncio.run_coroutine_threadsafe(
            _graceful_shutdown(node, strategy_id, stop_event),
            loop,
        )
        return "OK graceful shutdown started"

    if cmd == "kill":
        with state.lock:
            state.shutting_down = True
        state.push_log("command=kill accepted")
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
    log_publisher: LogPublisher | None = None,
) -> None:
    await node.kernel.start_async()
    node.trader.stop_strategy(strategy_id)

    loop = node.kernel.loop
    if loop is None:
        raise RuntimeError("No event loop on TradingNode")

    state = WorkerState(
        node_id=bootstrap.node_id,
        user_id=bootstrap.user_id,
        log_publisher=log_publisher,
    )
    state.push_log(f"trading node ready node_id={bootstrap.node_id}")
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
    log_publisher = _install_observe_logging(bootstrap)
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
        loop.run_until_complete(_run_node(node, strategy_id, bootstrap, log_publisher))
    except KeyboardInterrupt:
        if node.is_running():
            loop.run_until_complete(
                _graceful_shutdown(node, strategy_id, threading.Event()),
            )
