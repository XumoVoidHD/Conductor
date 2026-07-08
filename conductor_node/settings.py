"""Conductor Node settings."""
from __future__ import annotations

import os

from shared.env import REPO_ROOT
from shared.env import load_env_file

load_env_file()

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
COMMANDS_KEY = os.getenv("CONDUCTOR_COMMANDS_KEY", "conductor:commands")
EVENTS_KEY = os.getenv("CONDUCTOR_EVENTS_KEY", "conductor:events")
NODES_DIR = REPO_ROOT / os.getenv("CONDUCTOR_NODES_DIR", "data/nodes")
DEFAULT_CONTROL_HOST = os.getenv("CONTROL_HOST", "127.0.0.1")
CONTROL_PORT_BASE = int(os.getenv("CONDUCTOR_CONTROL_PORT_BASE", "9000"))
