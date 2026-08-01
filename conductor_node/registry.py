"""Track spawned trading nodes (subprocess or Docker container)."""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Literal

NodeRuntimeKind = Literal["subprocess", "docker"]


@dataclass
class RunningNode:
    node_id: str
    user_id: str
    control_host: str
    control_port: int
    broker_adapter: str
    bootstrap_path: str
    runtime: NodeRuntimeKind
    deploy_status: str = "DEPLOYED"
    process: subprocess.Popen[Any] | None = None
    container_id: str | None = None

    def is_alive(self) -> bool:
        if self.runtime == "docker":
            if not self.container_id:
                return False
            from conductor_node.docker_runtime import is_container_alive

            return is_container_alive(self.container_id)
        return self.process is not None and self.process.poll() is None


@dataclass
class NodeRegistry:
    _nodes: dict[str, RunningNode] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next_control_port: int = 9000
    # Ports handed out by allocate_control_port but not yet tied to a RunningNode
    # (or still held by a registered node). Prevents concurrent deploy races.
    _reserved_ports: set[int] = field(default_factory=set)

    def configure_port_base(self, control_port_base: int) -> None:
        self._next_control_port = control_port_base

    def allocate_control_port(self, requested: int | None, *, runtime: NodeRuntimeKind) -> int:
        """
        Allocate a unique control port for a new node.

        Ports are unique across *all* users and runtimes so Docker host binds
        (and local subprocess binds) never collide. Stopped-but-registered
        nodes keep their port reserved until delete.
        """
        with self._lock:
            if requested is not None:
                if self._port_taken(requested, runtime=runtime):
                    raise ValueError(f"control port {requested} is already in use")
                self._reserved_ports.add(requested)
                return requested

            start = self._next_control_port
            for _ in range(10_000):
                port = self._next_control_port
                self._next_control_port += 1
                if not self._port_taken(port, runtime=runtime):
                    self._reserved_ports.add(port)
                    return port
            raise ValueError(
                f"no free control ports from base {start} "
                f"(checked 10000 candidates for runtime={runtime})",
            )

    def release_control_port(self, port: int) -> None:
        """Free a port that was allocated but never registered (failed deploy)."""
        with self._lock:
            self._reserved_ports.discard(port)

    def _port_taken(self, port: int, *, runtime: NodeRuntimeKind) -> bool:
        if port in self._reserved_ports:
            return True
        if any(n.control_port == port for n in self._nodes.values()):
            return True
        if runtime == "docker":
            from conductor_node.docker_runtime import host_ports_in_use

            return port in host_ports_in_use()
        return False

    def add(self, node: RunningNode) -> None:
        with self._lock:
            if node.node_id in self._nodes and self._nodes[node.node_id].is_alive():
                raise ValueError(f"node_id {node.node_id} is already running")
            self._nodes[node.node_id] = node
            self._reserved_ports.add(node.control_port)

    def get(self, node_id: str) -> RunningNode | None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return None
            if not node.is_alive() and node.deploy_status not in {"INITIALIZING", "DEPLOYED"}:
                node.deploy_status = "STOPPED"
            return node

    def remove(self, node_id: str) -> RunningNode | None:
        with self._lock:
            node = self._nodes.pop(node_id, None)
            if node is not None:
                self._reserved_ports.discard(node.control_port)
            return node

    def list_for_user(self, user_id: str) -> list[RunningNode]:
        with self._lock:
            result: list[RunningNode] = []
            for node in self._nodes.values():
                if node.user_id != user_id:
                    continue
                if not node.is_alive() and node.deploy_status not in {"INITIALIZING", "DEPLOYED"}:
                    node.deploy_status = "STOPPED"
                result.append(node)
            return result

    def list_all(self) -> list[RunningNode]:
        with self._lock:
            for node in self._nodes.values():
                if not node.is_alive() and node.deploy_status not in {"INITIALIZING", "DEPLOYED"}:
                    node.deploy_status = "STOPPED"
            return list(self._nodes.values())
