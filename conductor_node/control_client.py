"""Send control commands to a trading node's TCP socket."""
from __future__ import annotations

import socket
import time


def send_control_command(
    host: str,
    port: int,
    command: str,
    *,
    timeout_sec: float = 5.0,
) -> str:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec) as sock:
            sock.sendall(f"{command}\n".encode("utf-8"))
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


def wait_for_control(
    host: str,
    port: int,
    *,
    timeout_sec: float = 45.0,
    interval_sec: float = 0.5,
) -> None:
    """Block until the node's control TCP port accepts connections."""
    deadline = time.monotonic() + timeout_sec
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2.0):
                return
        except OSError as exc:
            last_err = exc
            time.sleep(interval_sec)
    raise ConnectionError(
        f"control port {host}:{port} not ready after {timeout_sec:.0f}s"
        + (f" ({last_err})" if last_err else ""),
    )


def is_control_ready(host: str, port: int, *, timeout_sec: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except OSError:
        return False
