"""Send control commands to a trading node's TCP socket."""
from __future__ import annotations

import socket


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
            data = sock.recv(4096)
    except ConnectionRefusedError as exc:
        raise ConnectionError(f"cannot connect to trading node at {host}:{port}") from exc
    except OSError as exc:
        raise ConnectionError(f"control socket error ({host}:{port}): {exc}") from exc

    return data.decode("utf-8").strip()
