"""Conductor Node command handlers."""
from __future__ import annotations

from conductor_node.deploy import spawn_trading_node
from conductor_node.deploy import stop_trading_node
from conductor_node.registry import NodeRegistry
from conductor_node.schemas import ConductorCommand
from conductor_node.schemas import ConductorEvent
from conductor_node.schemas import parse_deploy_payload


class CommandHandler:
    def __init__(self, registry: NodeRegistry) -> None:
        self._registry = registry

    def handle(self, cmd: ConductorCommand) -> ConductorEvent:
        try:
            if cmd.command == "deploy":
                return self._deploy(cmd)
            if cmd.command == "stop":
                return self._stop(cmd)
            if cmd.command == "list":
                return self._list(cmd)
            return ConductorEvent(
                correlation_id=cmd.correlation_id,
                command=cmd.command,
                status="error",
                message=f"unknown command '{cmd.command}' (use deploy, stop, list)",
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

    def _deploy(self, cmd: ConductorCommand) -> ConductorEvent:
        payload = parse_deploy_payload(cmd)
        if cmd.user_id:
            payload.user_id = cmd.user_id
        if not payload.user_id:
            raise ValueError("user_id is required")

        running = spawn_trading_node(payload, self._registry)
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node deployed",
            user_id=running.user_id,
            node_id=running.node_id,
            data={
                "deploy_status": running.deploy_status,
                "control_host": running.control_host,
                "control_port": running.control_port,
                "broker_adapter": running.broker_adapter,
                "bootstrap_path": running.bootstrap_path,
                "pid": running.process.pid,
            },
        )

    def _stop(self, cmd: ConductorCommand) -> ConductorEvent:
        node_id = cmd.node_id or cmd.payload.get("node_id")
        if not node_id:
            raise ValueError("node_id is required for stop")

        node = self._registry.get(str(node_id))
        if node is None:
            raise ValueError(f"node {node_id} not found")

        if cmd.user_id and node.user_id != cmd.user_id:
            raise ValueError(f"node {node_id} does not belong to user {cmd.user_id}")

        graceful = bool(cmd.payload.get("graceful", True))
        stop_trading_node(node, graceful=graceful)
        self._registry.remove(node.node_id)

        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message="trading node stopped",
            user_id=node.user_id,
            node_id=node.node_id,
            data={"deploy_status": node.deploy_status},
        )

    def _list(self, cmd: ConductorCommand) -> ConductorEvent:
        user_id = cmd.user_id or cmd.payload.get("user_id")
        if not user_id:
            raise ValueError("user_id is required for list")

        nodes = self._registry.list_for_user(str(user_id))
        return ConductorEvent(
            correlation_id=cmd.correlation_id,
            command=cmd.command,
            status="ok",
            message=f"{len(nodes)} node(s)",
            user_id=str(user_id),
            data={
                "nodes": [
                    {
                        "node_id": n.node_id,
                        "user_id": n.user_id,
                        "deploy_status": n.deploy_status,
                        "alive": n.is_alive(),
                        "control_host": n.control_host,
                        "control_port": n.control_port,
                        "broker_adapter": n.broker_adapter,
                        "pid": n.process.pid if n.is_alive() else None,
                    }
                    for n in nodes
                ],
            },
        )
