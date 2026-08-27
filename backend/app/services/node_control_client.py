"""TCP client for trading-node control socket (API observe path).

Reads a full newline-terminated reply so large snapshot JSON is supported.
Backend talks to nodes directly on the Docker network — not via Conductor.
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


def _parse_summary_payload(reply: str) -> dict[str, Any]:
    if reply.startswith("ERROR"):
        raise RuntimeError(reply)
    prefix = "OK SUMMARY "
    if not reply.startswith(prefix):
        raise RuntimeError(f"unexpected summary reply: {reply[:200]}")
    payload = reply[len(prefix) :]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid summary JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("summary payload must be a JSON object")
    return data


def summary_from_full_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Derive a list-row summary from a full snapshot (older nodes without summary)."""
    node = snapshot.get("node") or {}
    strategy = snapshot.get("strategy") or {}
    positions = snapshot.get("positions") or {}
    orders = snapshot.get("orders") or {}
    health = snapshot.get("health") or {}
    return {
        "schema_version": 1,
        "kind": "summary",
        "captured_at": snapshot.get("captured_at"),
        "node_id": node.get("node_id"),
        "user_id": node.get("user_id"),
        "trader_id": node.get("trader_id"),
        "strategy": {
            "id": strategy.get("id"),
            "state": strategy.get("state") or health.get("strategy_state"),
        },
        "positions_open": int(positions.get("open_count") or len(positions.get("open") or [])),
        "orders_open": int(orders.get("open_count") or len(orders.get("open") or [])),
        "health": {
            "node_running": bool(health.get("node_running") or node.get("is_running")),
            "shutting_down": bool(health.get("shutting_down") or node.get("shutting_down")),
            "strategy_state": strategy.get("state") or health.get("strategy_state"),
        },
    }


def fetch_node_summary(host: str, port: int, *, timeout_sec: float = 8.0) -> dict[str, Any]:
    """
    Lightweight trader summary.

    Prefers TCP ``summary``; falls back to full ``snapshot`` + trim for older nodes.
    """
    try:
        reply = send_node_command(host, port, "summary", timeout_sec=timeout_sec)
        return _parse_summary_payload(reply)
    except RuntimeError:
        pass
    except ConnectionError:
        raise

    snapshot = fetch_node_snapshot(host, port, timeout_sec=max(timeout_sec, 15.0))
    return summary_from_full_snapshot(snapshot)
