"""Docker runtime for trading node containers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import docker
from docker.errors import APIError
from docker.errors import ImageNotFound
from docker.errors import NotFound
from docker.models.containers import Container
from docker.types import Mount

from conductor_node.settings import DOCKER_NETWORK
from conductor_node.settings import DOCKER_NODES_VOLUME
from conductor_node.settings import TRADING_NODE_CONTROL_PORT
from conductor_node.settings import TRADING_NODE_IMAGE


def container_name_for(node_id: str) -> str:
    return f"conductor-{node_id}"


def _client() -> docker.DockerClient:
    return docker.from_env()


def ensure_network() -> None:
    client = _client()
    try:
        client.networks.get(DOCKER_NETWORK)
    except NotFound:
        client.networks.create(DOCKER_NETWORK, driver="bridge")


def _remove_stale_container(client: docker.DockerClient, name: str) -> None:
    try:
        existing = client.containers.get(name)
    except NotFound:
        return
    if existing.status == "running":
        raise ValueError(f"container {name} is already running")
    existing.remove(force=True)


def spawn_trading_node_container(
    *,
    node_id: str,
    user_id: str,
    bootstrap_path: Path,
    control_port: int,
    publish_control_port: bool,
) -> Container:
    client = _client()
    ensure_network()

    name = container_name_for(node_id)
    _remove_stale_container(client, name)

    bootstrap_dir = bootstrap_path.parent.resolve()
    container_bootstrap = f"/app/data/nodes/{node_id}/bootstrap.json"
    bootstrap_json = bootstrap_path.read_text(encoding="utf-8")

    run_kwargs: dict[str, Any] = {
        "image": TRADING_NODE_IMAGE,
        "name": name,
        "detach": True,
        "network": DOCKER_NETWORK,
        "environment": {
            "CONDUCTOR_BOOTSTRAP": container_bootstrap,
            "CONDUCTOR_BOOTSTRAP_JSON": bootstrap_json,
            "CONTROL_BIND_HOST": "0.0.0.0",
        },
        "labels": {
            "conductor.stack": "trading",
            "conductor.role": "trading-node",
            "conductor.node_id": node_id,
            "conductor.user_id": user_id,
        },
        "extra_hosts": {"host.docker.internal": "host-gateway"},
    }

    if DOCKER_NODES_VOLUME:
        # Named volume — must use Mount(type="volume"). The volumes= dict treats
        # keys as host paths, not volume names.
        run_kwargs["mounts"] = [
            Mount(
                target="/app/data/nodes",
                source=DOCKER_NODES_VOLUME,
                type="volume",
                read_only=True,
            ),
        ]
    else:
        run_kwargs["volumes"] = {
            str(bootstrap_dir): {
                "bind": f"/app/data/nodes/{node_id}",
                "mode": "ro",
            },
        }

    if publish_control_port:
        run_kwargs["ports"] = {f"{control_port}/tcp": control_port}

    try:
        return client.containers.run(**run_kwargs)
    except ImageNotFound as exc:
        raise ValueError(
            f"trading node image not found: {TRADING_NODE_IMAGE} "
            "(build with: docker compose build trading-node)",
        ) from exc
    except APIError as exc:
        raise ValueError(f"docker run failed for {name}: {exc}") from exc


def _graceful_shutdown(
    container: Container,
    *,
    control_host: str,
    control_port: int,
) -> bool:
    """Ask the node to shut down via TCP. Returns True if the container exited."""
    if container.status != "running":
        return True
    try:
        from conductor_node.control_client import send_control_command

        send_control_command(control_host, control_port, "shutdown", timeout_sec=10.0)
        container.wait(timeout=20)
        return True
    except (ConnectionError, APIError):
        return False


def stop_trading_node_container(
    container_id: str,
    *,
    graceful: bool,
    control_host: str,
    control_port: int,
) -> None:
    """Stop the container but keep it (slot still occupied until delete)."""
    client = _client()
    try:
        container = client.containers.get(container_id)
    except NotFound:
        return

    if container.status != "running":
        return

    if graceful and _graceful_shutdown(
        container,
        control_host=control_host,
        control_port=control_port,
    ):
        return

    container.stop(timeout=15)


def start_trading_node_container(container_id: str) -> None:
    client = _client()
    try:
        container = client.containers.get(container_id)
    except NotFound as exc:
        raise ValueError(f"container {container_id} not found — redeploy the node") from exc
    if container.status == "running":
        return
    try:
        container.start()
    except APIError as exc:
        raise ValueError(f"docker start failed: {exc}") from exc


def restart_trading_node_container(container_id: str) -> None:
    client = _client()
    try:
        container = client.containers.get(container_id)
    except NotFound as exc:
        raise ValueError(f"container {container_id} not found — redeploy the node") from exc
    try:
        container.restart(timeout=15)
    except APIError as exc:
        raise ValueError(f"docker restart failed: {exc}") from exc


def delete_trading_node_container(
    container_id: str,
    *,
    graceful: bool,
    control_host: str,
    control_port: int,
) -> None:
    """Stop and remove the container (frees the user's node slot)."""
    client = _client()
    try:
        container = client.containers.get(container_id)
    except NotFound:
        return

    if graceful and container.status == "running":
        _graceful_shutdown(
            container,
            control_host=control_host,
            control_port=control_port,
        )

    try:
        container.reload()
        if container.status == "running":
            container.stop(timeout=15)
        container.remove(force=True)
    except NotFound:
        return
    except APIError as exc:
        raise ValueError(f"docker remove failed: {exc}") from exc


def is_container_alive(container_id: str) -> bool:
    client = _client()
    try:
        container = client.containers.get(container_id)
    except NotFound:
        return False
    return container.status == "running"


def container_exists(container_id: str) -> bool:
    client = _client()
    try:
        client.containers.get(container_id)
    except NotFound:
        return False
    return True
