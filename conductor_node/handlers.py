"""Conductor Node command handlers."""
from __future__ import annotations

from conductor_node.control_client import is_control_ready
from conductor_node.control_client import send_control_command
from conductor_node.control_client import wait_for_control
from conductor_node.deploy import delete_trading_node
from conductor_node.deploy import restart_trading_node
from conductor_node.deploy import spawn_trading_node
from conductor_node.deploy import start_trading_node
from conductor_node.deploy import stop_trading_node
from conductor_node.registry import NodeRegistry
from conductor_node.registry import RunningNode
from conductor_node.schemas import ConductorCommand
from conductor_node.schemas import ConductorEvent
from conductor_node.schemas import parse_deploy_payload

# Strategy TCP commands (node process must be running and control-ready).
STRATEGY_CONTROL_COMMANDS = frozenset({"halt", "reset"})


def _parse_strategy_state(control_reply: str) -> str | None:
    """Extract strategy=running|stopped|missing from a status reply."""
    text = control_reply.strip()
    marker = "strategy="
    idx = text.lower().find(marker)
    if idx < 0:
        return None
    value = text[idx + len(marker) :].split()[0].strip().lower()
    return value or None


def _probe_node(node: RunningNode) -> dict:
    """
    User-facing status for a node:
      Stopped      — container/process not running
      Initializing — process up but control socket not ready yet
      Ready        — control ready, strategy not running
      Running      — strategy running
    """
    alive = node.is_alive()
    base = {
        "node_id": node.node_id,
        "user_id": node.user_id,
        "alive": alive,
        "broker_adapter": node.broker_adapter,
        "control_host": node.control_host,
        "control_port": node.control_port,
    }
    if not alive:
        # Just after deploy/restart the container may not report running yet.
        if node.deploy_status in {"INITIALIZING", "DEPLOYED"}:
            return {
                **base,
                "status": "Initializing",
                "ready": False,
                "strategy": None,
                "deploy_status": "INITIALIZING",
            }
        node.deploy_status = "STOPPED"
        return {
            **base,
            "status": "Stopped",
            "ready": False,
            "strategy": None,
            "deploy_status": node.deploy_status,
        }

    if not is_control_ready(node.control_host, node.control_port):
        node.deploy_status = "INITIALIZING"
        return {
            **base,
            "status": "Initializing",
            "ready": False,
            "strategy": None,
            "deploy_status": node.deploy_status,
        }

    try:
        reply = send_control_command(
            node.control_host,
            node.control_port,
            "status",
            timeout_sec=3.0,
        )
    except ConnectionError:
        node.deploy_status = "INITIALIZING"
        return {
            **base,
            "status": "Initializing",
            "ready": False,
            "strategy": None,
            "deploy_status": node.deploy_status,
        }

    strategy = _parse_strategy_state(reply)
    if strategy == "running":
        display = "Running"
        node.deploy_status = "RUNNING"
    else:
        display = "Ready"
        node.deploy_status = "READY"

    return {
        **base,
        "status": display,
        "ready": True,
        "strategy": strategy,
        "deploy_status": node.deploy_status,
        "control_reply": reply,
    }


class CommandHandler:
    def __init__(self, registry: NodeRegistry) -> None:
        self._registry = registry

    def handle(self, cmd: ConductorCommand) -> ConductorEvent:
        try:
            if cmd.command == "deploy":
                return self._deploy(cmd)
            if cmd.command == "stop":
                return self._stop(cmd)
            if cmd.command == "delete":
                return self._delete(cmd)
            if cmd.command == "restart":
                return self._restart(cmd)
            if cmd.command == "run":
                return self._run(cmd)
            if cmd.command == "status":
                return self._status(cmd)
            if cmd.command == "list":
                return self._list(cmd)
            if cmd.command in STRATEGY_CONTROL_COMMANDS:
                return self._strategy_control(cmd)
            return ConductorEvent(
                correlation_id=cmd.correlation_id,
                command=cmd.command,
                status="error",
                message=(
                    f"unknown command '{cmd.command}' "
                    "(use deploy, stop, delete, restart, list, run, halt, status, reset)"
                ),
                user_id=cmd.user_id,
                node_id=cmd.node_id,
            )
        except Exception as exc:
            return ConductorEvent(
                correlation_id=cmd.correlation_id,
                command=cmd.command,
                status="error",
                message=str(exc),
                user_id=cmd.user_id,
                node_id=cmd.node_id,
            )

    def _get_owned_node(self, cmd: ConductorCommand, *, require_alive: bool) -> RunningNode:
        node_id = cmd.node_id or cmd.payload.get("node_id")
        if not node_id:
            raise ValueError("node_id is required")

        node = self._registry.get(str(node_id))
        if node is None:
            raise ValueError(f"node {node_id} not found")

        if cmd.user_id and node.user_id != cmd.user_id:
            raise ValueError(f"node {node_id} does not belong to user {cmd.user_id}")

        if require_alive and not node.is_alive():
            raise ValueError(f"node {node_id} is not running")

        return node

    def _require_node(self, cmd: ConductorCommand) -> RunningNode:
        return self._get_owned_node(cmd, require_alive=True)

    def _ensure_control_ready(self, node: RunningNode) -> None:
        """Start if needed, then wait until commands can be pushed."""
        if not node.is_alive():
            start_trading_node(node)
            return
        wait_for_control(node.control_host, node.control_port)

    def _node_data(self, node: RunningNode) -> dict:
        probed = _probe_node(node)
        return {
            "status": probed["status"],
            "ready": probed["ready"],
            "alive": probed["alive"],
            "strategy": probed.get("strategy"),
            "deploy_status": probed["deploy_status"],
            "broker_adapter": node.broker_adapter,
            "bootstrap_path": node.bootstrap_path,
            "control_host": node.control_host,
            "control_port": node.control_port,
            "control_reply": probed.get("control_reply"),
        }

    def _deploy(self, cmd: ConductorCommand) -> ConductorEvent:
        payload = parse_deploy_payload(cmd)
        if cmd.user_id:
            payload.user_id = cmd.user_id
        if not payload.user_id:
            raise ValueError("user_id is required")

        max_nodes = cmd.payload.get("max_trading_nodes")
        if max_nodes is not None:
            current = len(self._registry.list_for_user(payload.user_id))
            limit = int(max_nodes)
            if current >= limit:
                raise ValueError(
                    f"trading node limit reached ({current}/{limit}); "
                    "delete a node before deploying another",
                )

        running = spawn_trading_node(payload, self._registry)
        running.deploy_status = "INITIALIZING"
        data = {
            "status": "Initializing",
            "ready": False,
            "alive": running.is_alive(),
            "strategy": None,
            "deploy_status": "INITIALIZING",
            "broker_adapter": running.broker_adapter,
            "runtime": running.runtime,
            "control_host": running.control_host,
            "control_port": running.control_port,
            "container_id": running.container_id,
            "bootstrap_path": running.bootstrap_path,
        }
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node deployed — initializing until control is ready",
            user_id=running.user_id,
            node_id=running.node_id,
            data=data,
        )

    def _drop_gone_node(self, node: RunningNode, message: str) -> None:
        """Container disappeared — free Conductor registry slot."""
        self._registry.remove(node.node_id)
        raise ValueError(message)

    def _require_docker_container(self, node: RunningNode) -> None:
        if node.runtime != "docker":
            return
        from conductor_node.docker_runtime import container_exists

        if not node.container_id or not container_exists(node.container_id):
            self._drop_gone_node(
                node,
                f"container {node.container_id or node.node_id} not found — redeploy the node",
            )

    def _stop(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._get_owned_node(cmd, require_alive=False)
        self._require_docker_container(node)
        graceful = bool(cmd.payload.get("graceful", True))
        try:
            stop_trading_node(node, graceful=graceful)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                self._drop_gone_node(node, str(exc))
            raise

        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node stopped (slot still reserved — use delete to free)",
            user_id=node.user_id,
            node_id=node.node_id,
            data=self._node_data(node),
        )

    def _delete(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._get_owned_node(cmd, require_alive=False)
        graceful = bool(cmd.payload.get("graceful", True))
        delete_trading_node(node, graceful=graceful)
        self._registry.remove(node.node_id)

        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node deleted",
            user_id=node.user_id,
            node_id=node.node_id,
            data={"status": "Deleted", "deploy_status": "DELETED"},
        )

    def _restart(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._get_owned_node(cmd, require_alive=False)
        self._require_docker_container(node)
        try:
            restart_trading_node(node)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                self._drop_gone_node(node, str(exc))
            raise
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node restarted (strategy Ready — call run)",
            user_id=node.user_id,
            node_id=node.node_id,
            data=self._node_data(node),
        )

    def _run(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._get_owned_node(cmd, require_alive=False)
        self._require_docker_container(node)
        try:
            self._ensure_control_ready(node)
        except ValueError as exc:
            if "not found" in str(exc).lower():
                self._drop_gone_node(node, str(exc))
            raise
        reply = send_control_command(node.control_host, node.control_port, "run")
        status = "ok" if reply.startswith("OK") else "error"
        data = self._node_data(node)
        data["control_reply"] = reply
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status=status,
            message=reply,
            user_id=node.user_id,
            node_id=node.node_id,
            data=data,
        )

    def _status(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._get_owned_node(cmd, require_alive=False)
        data = self._node_data(node)
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message=data.get("control_reply") or data["status"],
            user_id=node.user_id,
            node_id=node.node_id,
            data=data,
        )

    def _list(self, cmd: ConductorCommand) -> ConductorEvent:
        user_id = cmd.user_id or cmd.payload.get("user_id")
        if not user_id:
            raise ValueError("user_id is required for list")

        nodes = self._registry.list_for_user(str(user_id))
        probed = [_probe_node(n) for n in nodes]
        public_nodes = [
            {
                "node_id": p["node_id"],
                "status": p["status"],
                "alive": p["alive"],
                "ready": p["ready"],
                "strategy": p.get("strategy"),
                "broker_adapter": p["broker_adapter"],
                "deploy_status": p["deploy_status"],
            }
            for p in probed
        ]
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message=f"{len(public_nodes)} node(s)",
            user_id=str(user_id),
            data={
                "nodes": public_nodes,
                "node_count": len(public_nodes),
            },
        )

    def _strategy_control(self, cmd: ConductorCommand) -> ConductorEvent:
        node = self._require_node(cmd)
        self._ensure_control_ready(node)
        reply = send_control_command(node.control_host, node.control_port, cmd.command)

        status = "ok" if reply.startswith("OK") else "error"
        data = self._node_data(node)
        data["control_reply"] = reply
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status=status,
            message=reply,
            user_id=node.user_id,
            node_id=node.node_id,
            data=data,
        )
