"""TCP client for trading-node control socket (used by API observe path).

Reads a full newline-terminated reply so large snapshot JSON is supported.
"""
from __future__ import annotations

import json
import socket
from typing import Any


def send_node_command(
    host: str,
    port: int,
    command: str,
    *,
    timeout_sec: float = 20.0,
) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.sendall(f"{command.strip().lower()}\n".encode("utf-8"))
            sock.settimeout(timeout_sec)
            chunks: list[bytes] = []
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                chunks.append(data)
                if b"\n" in data:
                    break
    except ConnectionRefusedError as exc:
        raise ConnectionError(f"cannot connect to trading node at {host}:{port}") from exc
    except OSError as exc:
        raise ConnectionError(f"control socket error ({host}:{port}): {exc}") from exc

    return b"".join(chunks).decode("utf-8").strip()


def fetch_node_snapshot(host: str, port: int, *, timeout_sec: float = 20.0) -> dict[str, Any]:
    """Request a full node snapshot over the control TCP socket."""
    reply = send_node_command(host, port, "snapshot", timeout_sec=timeout_sec)
    if reply.startswith("ERROR"):
        raise RuntimeError(reply)
    prefix = "OK SNAPSHOT "
    if not reply.startswith(prefix):
        raise RuntimeError(f"unexpected snapshot reply: {reply[:200]}")
    payload = reply[len(prefix) :]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid snapshot JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("snapshot payload must be a JSON object")
    return data
