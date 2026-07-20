"""Thin Redis client for Conductor command/event lists."""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

import redis
from fastapi import HTTPException
from fastapi import status

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ConductorClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._settings = settings
        self._client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=5,
        )
        self._commands_key = settings.conductor_commands_key
        self._events_key = settings.conductor_events_key

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except redis.RedisError:
            return False

    def enqueue(self, command: dict[str, Any]) -> str:
        correlation_id = str(command.get("correlation_id") or uuid.uuid4())
        command["correlation_id"] = correlation_id
        try:
            self._client.lpush(self._commands_key, json.dumps(command))
        except redis.RedisError as exc:
            logger.exception("Failed to enqueue Conductor command")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot reach Redis: {exc}",
            ) from exc
        logger.info(
            "Enqueued conductor command=%s correlation_id=%s",
            command.get("command"),
            correlation_id,
        )
        return correlation_id

    def wait_for_event(
        self,
        correlation_id: str,
        *,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        timeout = (
            self._settings.conductor_event_timeout_sec
            if timeout_sec is None
            else timeout_sec
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for event in self.fetch_recent_events(count=30):
                if event.get("correlation_id") == correlation_id:
                    return event
            time.sleep(0.25)

        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "Timed out waiting for Conductor event. "
                "Is `python -m conductor_node` running?"
            ),
        )

    def enqueue_and_wait(self, command: dict[str, Any]) -> dict[str, Any]:
        correlation_id = self.enqueue(command)
        return self.wait_for_event(correlation_id)

    def fetch_recent_events(self, count: int = 20) -> list[dict[str, Any]]:
        try:
            raw_items = self._client.lrange(self._events_key, 0, count - 1)
        except redis.RedisError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cannot read Redis events: {exc}",
            ) from exc
        return [json.loads(item) for item in raw_items]
