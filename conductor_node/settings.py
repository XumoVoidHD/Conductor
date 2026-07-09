"""Conductor Node settings."""
from __future__ import annotations

import os
from pathlib import Path

from shared.env import REPO_ROOT
from shared.env import load_env_file

load_env_file()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
COMMANDS_KEY = os.getenv("CONDUCTOR_COMMANDS_KEY", "conductor:commands")
EVENTS_KEY = os.getenv("CONDUCTOR_EVENTS_KEY", "conductor:events")
_nodes_dir_env = os.getenv("CONDUCTOR_NODES_DIR", "data/nodes")
NODES_DIR = Path(_nodes_dir_env) if os.path.isabs(_nodes_dir_env) else REPO_ROOT / _nodes_dir_env
DEFAULT_CONTROL_HOST = os.getenv("CONTROL_HOST", "127.0.0.1")
CONTROL_PORT_BASE = int(os.getenv("CONDUCTOR_CONTROL_PORT_BASE", "9000"))

# subprocess (local dev) | docker (Conductor spawns sibling containers)
NODE_RUNTIME = os.getenv("CONDUCTOR_NODE_RUNTIME", "subprocess").strip().lower()
TRADING_NODE_IMAGE = os.getenv("TRADING_NODE_IMAGE", "conductor-trading-node:latest")
DOCKER_NETWORK = os.getenv("DOCKER_NETWORK", "conductor-net")
TRADING_NODE_CONTROL_PORT = int(os.getenv("TRADING_NODE_CONTROL_PORT", "9000"))
DOCKER_PUBLISH_CONTROL_PORT = os.getenv("DOCKER_PUBLISH_CONTROL_PORT", "false").lower() in {
    "1",
    "true",
    "yes",
}
# Named Docker volume for node bootstrap files (required when Conductor runs in Docker).
DOCKER_NODES_VOLUME = os.getenv("DOCKER_NODES_VOLUME", "").strip() or None
