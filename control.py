#!/usr/bin/env python3
"""
Send commands to a running worker.py process.

Usage (from Conductor repo root, in a second terminal):

    python control.py run        # start strategy
    python control.py stop       # stop strategy
    python control.py status     # check state
    python control.py shutdown   # graceful worker exit
    python control.py kill       # emergency immediate exit
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


def _load_env_file() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def send_command(command: str) -> str:
    host = os.getenv("CONTROL_HOST", "127.0.0.1")
    port = int(os.getenv("CONTROL_PORT", "8765"))

    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            sock.sendall(f"{command}\n".encode("utf-8"))
            sock.settimeout(5)
            data = sock.recv(4096)
    except ConnectionRefusedError:
        raise SystemExit(
            f"Cannot connect to worker at {host}:{port} — is worker.py running?",
        ) from None
    except OSError as exc:
        raise SystemExit(f"Control socket error: {exc}") from exc

    return data.decode("utf-8").strip()


def main() -> None:
    _load_env_file()

    parser = argparse.ArgumentParser(description="Control a running worker.py")
    parser.add_argument(
        "command",
        choices=["run", "stop", "status", "shutdown", "kill"],
        help=(
            "run=start strategy, stop=stop strategy, status=check state, "
            "shutdown=graceful worker stop, kill=immediate worker stop"
        ),
    )
    args = parser.parse_args()

    reply = send_command(args.command)
    print(reply)

    if reply.startswith("ERROR"):
        sys.exit(1)


if __name__ == "__main__":
    main()
