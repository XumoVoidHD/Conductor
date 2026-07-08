"""Track spawned trading node processes."""
from __future__ import annotations

import subprocess
import threading
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class RunningNode:
    node_id: str
    user_id: str
    process: subprocess.Popen[Any]
    control_host: str
    control_port: int
    broker_adapter: str
    bootstrap_path: str
    deploy_status: str = "DEPLOYED"

    def is_alive(self) -> bool:
        return self.process.poll() is None


@dataclass
class NodeRegistry:
    _nodes: dict[str, RunningNode] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _next_control_port: int = 9000

    def configure_port_base(self, control_port_base: int) -> None:
        self._next_control_port = control_port_base

    def allocate_control_port(self, requested: int | None) -> int:
        with self._lock:
            if requested is not None:
                return requested
            while self._port_in_use(self._next_control_port):
                self._next_control_port += 1
            port = self._next_control_port
            self._next_control_port += 1
            return port

    def _port_in_use(self, port: int) -> bool:
        return any(n.control_port == port and n.is_alive() for n in self._nodes.values())

    def add(self, node: RunningNode) -> None:
        with self._lock:
            if node.node_id in self._nodes and self._nodes[node.node_id].is_alive():
                raise ValueError(f"node_id {node.node_id} is already running")
            self._nodes[node.node_id] = node

    def get(self, node_id: str) -> RunningNode | None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return None
            if not node.is_alive():
                node.deploy_status = "STOPPED"
            return node

    def remove(self, node_id: str) -> RunningNode | None:
        with self._lock:
            return self._nodes.pop(node_id, None)

    def list_for_user(self, user_id: str) -> list[RunningNode]:
        with self._lock:
            result: list[RunningNode] = []
            for node in self._nodes.values():
                if node.user_id != user_id:
                    continue
                if not node.is_alive():
                    node.deploy_status = "STOPPED"
                result.append(node)
            return result

    def list_all(self) -> list[RunningNode]:
        with self._lock:
            for node in self._nodes.values():
                if not node.is_alive():
                    node.deploy_status = "STOPPED"
            return list(self._nodes.values())
