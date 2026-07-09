"""Spawn trading nodes as subprocesses or Docker containers."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

from conductor_node.docker_runtime import container_name_for
from conductor_node.docker_runtime import spawn_trading_node_container
from conductor_node.docker_runtime import stop_trading_node_container
from conductor_node.registry import NodeRegistry
from conductor_node.registry import RunningNode
from conductor_node.schemas import DeployPayload
from conductor_node.settings import DEFAULT_CONTROL_HOST
from conductor_node.settings import DOCKER_PUBLISH_CONTROL_PORT
from conductor_node.settings import NODE_RUNTIME
from conductor_node.settings import NODES_DIR
from shared.env import REPO_ROOT


def _new_node_id() -> str:
    return f"tn-{uuid.uuid4().hex[:8]}"


def build_bootstrap_dict(
    payload: DeployPayload,
    *,
    node_id: str,
    control_port: int,
    control_host: str,
) -> dict[str, Any]:
    assert payload.broker is not None
    assert payload.strategy is not None

    trader_id = payload.trader_id or f"CONDUCTOR-{node_id.upper()}"

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


def _control_host_for_runtime(
    payload: DeployPayload,
    *,
    node_id: str,
    runtime: str,
) -> str:
    if runtime == "docker":
        return container_name_for(node_id)
    return payload.control_host or DEFAULT_CONTROL_HOST


def spawn_trading_node(
    payload: DeployPayload,
    registry: NodeRegistry,
) -> RunningNode:
    if not payload.user_id:
        raise ValueError("user_id is required")

    runtime = NODE_RUNTIME
    if runtime not in ("subprocess", "docker"):
        raise ValueError(f"unsupported CONDUCTOR_NODE_RUNTIME: {runtime}")
    node_id = payload.node_id or _new_node_id()
    existing = registry.get(node_id)
    if existing is not None and existing.is_alive():
        raise ValueError(f"node {node_id} is already running")

    assert payload.broker is not None
    control_port = registry.allocate_control_port(payload.control_port, runtime=runtime)
    control_host = _control_host_for_runtime(payload, node_id=node_id, runtime=runtime)

    bootstrap = build_bootstrap_dict(
        payload,
        node_id=node_id,
        control_port=control_port,
        control_host=control_host,
    )
    bootstrap_path = write_bootstrap(node_id, bootstrap)

    if runtime == "docker":
        container = spawn_trading_node_container(
            node_id=node_id,
            user_id=payload.user_id,
            bootstrap_path=bootstrap_path,
            control_port=control_port,
            publish_control_port=DOCKER_PUBLISH_CONTROL_PORT,
        )
        running = RunningNode(
            node_id=node_id,
            user_id=payload.user_id,
            control_host=control_host,
            control_port=control_port,
            broker_adapter=payload.broker.adapter,
            bootstrap_path=str(bootstrap_path),
            runtime="docker",
            container_id=container.id,
            deploy_status="DEPLOYED",
        )
        registry.add(running)
        return running

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
        control_host=control_host,
        control_port=control_port,
        broker_adapter=payload.broker.adapter,
        bootstrap_path=str(bootstrap_path),
        runtime="subprocess",
        process=process,
        deploy_status="DEPLOYED",
    )
    registry.add(running)
    return running


def stop_trading_node(node: RunningNode, *, graceful: bool = True) -> None:
    if not node.is_alive():
        node.deploy_status = "STOPPED"
        return

    if node.runtime == "docker":
        assert node.container_id is not None
        stop_trading_node_container(
            node.container_id,
            graceful=graceful,
            control_host=node.control_host,
            control_port=node.control_port,
        )
        node.deploy_status = "STOPPED"
        return

    assert node.process is not None

    if graceful:
        try:
            from conductor_node.control_client import send_control_command

            send_control_command(node.control_host, node.control_port, "shutdown", timeout_sec=10.0)
        except ConnectionError:
            node.process.terminate()
    else:
        try:
            from conductor_node.control_client import send_control_command

            send_control_command(node.control_host, node.control_port, "kill", timeout_sec=5.0)
        except ConnectionError:
            node.process.kill()

    try:
        node.process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        node.process.kill()
        node.process.wait(timeout=5)

    node.deploy_status = "STOPPED"
