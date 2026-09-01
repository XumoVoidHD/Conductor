"""Publish observe events (logs) to Redis Streams."""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from datetime import timezone
from typing import Any

import redis

OBSERVE_EVENTS_STREAM = os.getenv("OBSERVE_EVENTS_STREAM", "observe:events")
OBSERVE_STREAM_MAXLEN = int(os.getenv("OBSERVE_STREAM_MAXLEN", "10000"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LogPublisher:
    """Thread-safe Redis Stream publisher for trading-node log lines."""

    def __init__(
        self,
        *,
        redis_url: str,
        user_id: str,
        node_id: str,
        stream_key: str = OBSERVE_EVENTS_STREAM,
    ) -> None:
        self._user_id = user_id
        self._node_id = node_id
        self._stream_key = stream_key
        self._lock = threading.Lock()
        self._client: redis.Redis | None = None
        self._redis_url = redis_url
        self._enabled = bool(redis_url.strip())

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
        return self._client

    def publish_log(self, message: str, *, level: str = "INFO") -> None:
        if not self._enabled:
            return
        line = (message or "").rstrip("\n")
        if not line:
            return
        fields: dict[str, Any] = {
            "type": "log",
            "user_id": self._user_id,
            "node_id": self._node_id,
            "level": level,
            "line": line,
            "ts": _now_iso(),
        }
        try:
            with self._lock:
                self._get_client().xadd(
                    self._stream_key,
                    fields,
                    maxlen=OBSERVE_STREAM_MAXLEN,
                    approximate=True,
                )
        except redis.RedisError:
            # Observe must never break the trading node.
            pass

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                try:
                    self._client.close()
                except Exception:  # noqa: BLE001
                    pass
                self._client = None


class RedisLogHandler(logging.Handler):
    """Forward Python log records to LogPublisher."""

    def __init__(self, publisher: LogPublisher) -> None:
        super().__init__()
        self._publisher = publisher

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._publisher.publish_log(msg, level=record.levelname)
        except Exception:  # noqa: BLE001
            self.handleError(record)


def build_log_publisher(*, user_id: str, node_id: str) -> LogPublisher | None:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    return LogPublisher(redis_url=redis_url, user_id=user_id, node_id=node_id)
