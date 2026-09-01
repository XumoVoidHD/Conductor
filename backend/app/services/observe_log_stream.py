"""Consume observe log events from Redis Streams for WebSocket clients."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

OBSERVE_EVENTS_STREAM = "observe:events"


class ObserveLogStreamService:
    def __init__(self) -> None:
        settings = get_settings()
        self._redis_url = settings.redis_url
        self._stream_key = settings.observe_events_stream

    async def stream_logs(
        self,
        *,
        user_id: str,
        node_id: str,
        last_id: str = "$",
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Yield log events for one node owned by user_id.

        Uses XREAD BLOCK on observe:events and filters by user_id + node_id + type=log.
        """
        client = aioredis.from_url(
            self._redis_url,
            decode_responses=True,
        )
        cursor = last_id
        try:
            while True:
                try:
                    rows = await client.xread(
                        {self._stream_key: cursor},
                        block=5000,
                        count=50,
                    )
                except asyncio.CancelledError:
                    raise
                except Exception:
                    await asyncio.sleep(1.0)
                    continue

                if not rows:
                    continue

                for _stream, messages in rows:
                    for msg_id, fields in messages:
                        cursor = msg_id
                        if fields.get("type") != "log":
                            continue
                        if fields.get("user_id") != user_id:
                            continue
                        if fields.get("node_id") != node_id:
                            continue
                        yield {
                            "id": msg_id,
                            "ts": fields.get("ts"),
                            "level": fields.get("level", "INFO"),
                            "line": fields.get("line", ""),
                        }
        finally:
            await client.aclose()
