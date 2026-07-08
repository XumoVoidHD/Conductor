"""Redis command queue and event publishing."""
from __future__ import annotations

import json
from typing import Any

import redis

from conductor_node.schemas import ConductorEvent
from conductor_node.settings import COMMANDS_KEY
from conductor_node.settings import EVENTS_KEY
from conductor_node.settings import REDIS_URL


class RedisBus:
    def __init__(self, url: str = REDIS_URL) -> None:
        # socket_timeout=None — BRPOP manages its own wait; avoids false TimeoutError on idle poll
        self._client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=None)

    def ping(self) -> bool:
        return bool(self._client.ping())

    def enqueue_command(self, command: dict[str, Any]) -> None:
        self._client.lpush(COMMANDS_KEY, json.dumps(command))

    def blocking_dequeue_command(self, timeout_sec: int = 5) -> dict[str, Any] | None:
        try:
            result = self._client.brpop(COMMANDS_KEY, timeout=timeout_sec)
        except redis.exceptions.TimeoutError:
            # redis-py can raise on BRPOP idle timeout instead of returning None
            return None
        if result is None:
            return None
        _key, raw = result
        return json.loads(raw)

    def publish_event(self, event: ConductorEvent) -> None:
        self._client.lpush(EVENTS_KEY, json.dumps(event.to_dict()))

    def fetch_recent_events(self, count: int = 10) -> list[dict[str, Any]]:
        raw_items = self._client.lrange(EVENTS_KEY, 0, count - 1)
        return [json.loads(item) for item in raw_items]
