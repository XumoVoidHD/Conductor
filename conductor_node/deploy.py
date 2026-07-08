"""Spawn trading node subprocesses from bootstrap payloads."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from conductor_node.registry import NodeRegistry
from conductor_node.registry import RunningNode
from conductor_node.schemas import DeployPayload
from conductor_node.settings import DEFAULT_CONTROL_HOST
from conductor_node.settings import NODES_DIR
from shared.env import REPO_ROOT


def _new_node_id() -> str:
    return f"tn-{uuid.uuid4().hex[:8]}"


def build_bootstrap_dict(
    payload: DeployPayload,
    *,
    node_id: str,
    control_port: int,
) -> dict[str, Any]:
    assert payload.broker is not None
    assert payload.strategy is not None

    trader_id = payload.trader_id or f"CONDUCTOR-{node_id.upper()}"
    control_host = payload.control_host or DEFAULT_CONTROL_HOST

    return {
        "node_id": node_id,
        "user_id": payload.user_id,
        "trader_id": trader_id,
        "control_host": control_host,
        "control_port": control_port,
        "broker": {
            "adapter": payload.broker.adapter,
            "config": dict(payload.broker.config),
        },
        "strategy": {
            "module": payload.strategy.module,
            "class_name": payload.strategy.class_name,
            "config_class": payload.strategy.config_class,
        },
    }


def write_bootstrap(node_id: str, bootstrap: dict[str, Any]) -> Path:
    node_dir = NODES_DIR / node_id
    node_dir.mkdir(parents=True, exist_ok=True)
    path = node_dir / "bootstrap.json"
    path.write_text(json.dumps(bootstrap, indent=2), encoding="utf-8")
    return path


def spawn_trading_node(
    payload: DeployPayload,
    registry: NodeRegistry,
) -> RunningNode:
    if not payload.user_id:
        raise ValueError("user_id is required")

    node_id = payload.node_id or _new_node_id()
    existing = registry.get(node_id)
    if existing is not None and existing.is_alive():
        raise ValueError(f"node {node_id} is already running")

    assert payload.broker is not None
    control_port = registry.allocate_control_port(payload.control_port)

    bootstrap = build_bootstrap_dict(
        payload,
        node_id=node_id,
        control_port=control_port,
    )
    bootstrap_path = write_bootstrap(node_id, bootstrap)

    env = os.environ.copy()
    env["CONDUCTOR_BOOTSTRAP"] = str(bootstrap_path)
    env["PYTHONPATH"] = str(REPO_ROOT)

    process = subprocess.Popen(
        [sys.executable, "-m", "trading_node"],
        cwd=str(REPO_ROOT),
        env=env,
    )

    running = RunningNode(
        node_id=node_id,
        user_id=payload.user_id,
        process=process,
        control_host=bootstrap["control_host"],
        control_port=control_port,
        broker_adapter=payload.broker.adapter,
        bootstrap_path=str(bootstrap_path),
        deploy_status="DEPLOYED",
    )
    registry.add(running)
    return running


def stop_trading_node(node: RunningNode, *, graceful: bool = True) -> None:
    if not node.is_alive():
        node.deploy_status = "STOPPED"
        return

    if graceful:
        try:
            import socket

            with socket.create_connection((node.control_host, node.control_port), timeout=3) as sock:
                sock.sendall(b"shutdown\n")
                sock.settimeout(5)
                sock.recv(4096)
        except OSError:
            node.process.terminate()
    else:
        try:
            import socket

            with socket.create_connection((node.control_host, node.control_port), timeout=3) as sock:
                sock.sendall(b"kill\n")
        except OSError:
            node.process.kill()

    try:
        node.process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        node.process.kill()
        node.process.wait(timeout=5)

    node.deploy_status = "STOPPED"
