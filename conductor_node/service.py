"""Conductor Node service loop."""
from __future__ import annotations

from conductor_node.handlers import CommandHandler
from conductor_node.registry import NodeRegistry
from conductor_node.schemas import ConductorCommand
from conductor_node.settings import CONTROL_PORT_BASE
from conductor_node.settings import COMMANDS_KEY
from conductor_node.settings import EVENTS_KEY
from conductor_node.settings import REDIS_URL
from conductor_node.redis_bus import RedisBus


def run() -> None:
    bus = RedisBus()
    if not bus.ping():
        raise SystemExit(f"Cannot connect to Redis at {REDIS_URL}")

    registry = NodeRegistry()
    registry.configure_port_base(CONTROL_PORT_BASE)
    handler = CommandHandler(registry)

    print("=" * 60)
    print("Conductor Node")
    print(f"Redis: {REDIS_URL}")
    print(f"Commands queue: {COMMANDS_KEY}")
    print(f"Events queue:   {EVENTS_KEY}")
    print("Waiting for deploy | stop | list commands...")
    print("=" * 60)

    while True:
        raw = bus.blocking_dequeue_command(timeout_sec=5)
        if raw is None:
            continue

        cmd = ConductorCommand.from_dict(raw)
        print(f"Command: {cmd.command} correlation_id={cmd.correlation_id} user_id={cmd.user_id}")

        event = handler.handle(cmd)
        bus.publish_event(event)
        print(f"Event: {event.status} — {event.message} (node_id={event.node_id})")
