"""
RunningPing — dev-only heartbeat strategy.

Prints "running" every 10 seconds via time.sleep in a background thread.
No subscriptions, orders, or market data — just to confirm the node is alive.
"""
from __future__ import annotations

import threading
import time

from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy

_INTERVAL_SEC = 10


class RunningPingConfig(StrategyConfig, frozen=True):
    """Configuration for ``RunningPing``."""


class RunningPing(Strategy):
    def __init__(self, config: RunningPingConfig) -> None:
        super().__init__(config)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def on_start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._thread.start()
        self.log.info(f"RunningPing started (every {_INTERVAL_SEC}s)")

    def _ping_loop(self) -> None:
        while not self._stop_event.is_set():
            print("running", flush=True)
            time.sleep(_INTERVAL_SEC)

    def on_stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=_INTERVAL_SEC + 1.0)
            self._thread = None
        self.log.info("RunningPing stopped")
