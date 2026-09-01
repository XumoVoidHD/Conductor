"""Stream full container stdout/stderr like ``docker logs -f``."""
from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator

import docker
from docker.errors import APIError
from docker.errors import NotFound


class DockerLogStreamService:
    async def stream_logs(self, container_ref: str) -> AsyncIterator[str]:
        """
        Yield log lines from a trading-node container (history + follow).

        Mirrors ``docker logs -f --tail all <container>``.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        stop = threading.Event()

        def worker() -> None:
            try:
                client = docker.from_env()
                container = client.containers.get(container_ref)
                buffer = ""
                for chunk in container.logs(
                    stream=True,
                    follow=True,
                    tail="all",
                    stdout=True,
                    stderr=True,
                ):
                    if stop.is_set():
                        break
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        asyncio.run_coroutine_threadsafe(queue.put(line), loop)
                if buffer:
                    asyncio.run_coroutine_threadsafe(queue.put(buffer.rstrip("\n")), loop)
            except NotFound:
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"[docker] container '{container_ref}' not found"),
                    loop,
                )
            except APIError as exc:
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"[docker] {exc.explanation or exc}"),
                    loop,
                )
            except Exception as exc:  # noqa: BLE001
                asyncio.run_coroutine_threadsafe(
                    queue.put(f"[docker] {exc}"),
                    loop,
                )
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        thread = threading.Thread(target=worker, daemon=True, name="docker-log-stream")
        thread.start()
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            stop.set()
