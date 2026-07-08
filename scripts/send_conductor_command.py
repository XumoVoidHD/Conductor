#!/usr/bin/env python3
"""
Send commands to Conductor Node via Redis (temporary — API will replace this).

The deploy command must be complete: broker.adapter + full broker.config + strategy.
Conductor does not allocate broker credentials or IBKR client ids.

Examples (from repo root):

    python scripts/send_conductor_command.py deploy --user-id alice
    python scripts/send_conductor_command.py list --user-id alice
    python scripts/send_conductor_command.py stop --user-id alice --node-id tn-demo01
    python scripts/send_conductor_command.py events
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from conductor_node.redis_bus import RedisBus
from conductor_node.settings import EVENTS_KEY
from shared.env import load_env_file


def _build_deploy_command(args: argparse.Namespace) -> dict:
    """Build a complete standardized deploy command (client fills broker config)."""
    account_id = args.account_id or os.getenv("TWS_ACCOUNT")
    if not account_id:
        raise SystemExit("account_id required (--account-id or TWS_ACCOUNT in .env)")

    ib_host = args.ib_host or os.getenv("IB_HOST", "127.0.0.1")
    ib_port = args.ib_port if args.ib_port is not None else int(os.getenv("IB_PORT", "7497"))
    ib_client_id = (
        args.ib_client_id
        if args.ib_client_id is not None
        else int(os.getenv("IB_CLIENT_ID", "20"))
    )

    strategy_module = args.strategy_module or "strategies.running_ping"
    strategy_class = args.strategy_class or "RunningPing"
    strategy_config_class = args.strategy_config_class or "RunningPingConfig"

    if args.ib_symbol:
        load_contracts = [
            {
                "secType": "STK",
                "symbol": args.ib_symbol,
                "exchange": args.ib_exchange or "SMART",
                "currency": args.ib_currency or "USD",
            },
        ]
    else:
        load_contracts = [
            {"secType": "STK", "symbol": "AAPL", "exchange": "SMART", "currency": "USD"},
        ]

    # Standardized deploy shape. For interactive_brokers, config must include
    # everything trading_node/brokers/interactive_brokers.py needs.
    payload: dict = {
        "broker": {
            "adapter": "interactive_brokers",
            "config": {
                "account_id": account_id,
                "ibg_host": ib_host,
                "ibg_port": ib_port,
                "ibg_client_id": ib_client_id,
                "load_contracts": load_contracts,
            },
        },
        "strategy": {
            "module": strategy_module,
            "class_name": strategy_class,
            "config_class": strategy_config_class,
        },
    }

    if args.control_port is not None:
        payload["control_port"] = args.control_port

    cmd = {
        "command": "deploy",
        "correlation_id": args.correlation_id or str(uuid.uuid4()),
        "user_id": args.user_id,
        "payload": payload,
    }
    if args.node_id:
        cmd["node_id"] = args.node_id
    return cmd


def main() -> None:
    load_env_file()

    parser = argparse.ArgumentParser(description="Send Conductor Node Redis commands")
    sub = parser.add_subparsers(dest="action", required=True)

    deploy = sub.add_parser("deploy", help="Deploy a trading node")
    deploy.add_argument("--user-id", required=True)
    deploy.add_argument("--node-id")
    deploy.add_argument("--correlation-id")
    deploy.add_argument("--account-id")
    deploy.add_argument("--ib-host")
    deploy.add_argument("--ib-port", type=int)
    deploy.add_argument("--ib-client-id", type=int)
    deploy.add_argument("--ib-symbol")
    deploy.add_argument("--ib-exchange")
    deploy.add_argument("--ib-currency")
    deploy.add_argument("--strategy-module")
    deploy.add_argument("--strategy-class")
    deploy.add_argument("--strategy-config-class")
    deploy.add_argument("--control-port", type=int)

    stop = sub.add_parser("stop", help="Stop a trading node")
    stop.add_argument("--user-id", required=True)
    stop.add_argument("--node-id", required=True)
    stop.add_argument("--correlation-id")
    stop.add_argument("--no-graceful", action="store_true")

    list_cmd = sub.add_parser("list", help="List nodes for a user")
    list_cmd.add_argument("--user-id", required=True)
    list_cmd.add_argument("--correlation-id")

    events = sub.add_parser("events", help="Show recent Conductor events")
    events.add_argument("--count", type=int, default=5)

    args = parser.parse_args()
    bus = RedisBus()

    if args.action == "events":
        for item in bus.fetch_recent_events(count=args.count):
            print(json.dumps(item, indent=2))
        return

    if args.action == "deploy":
        command = _build_deploy_command(args)
    elif args.action == "stop":
        command = {
            "command": "stop",
            "correlation_id": args.correlation_id or str(uuid.uuid4()),
            "user_id": args.user_id,
            "node_id": args.node_id,
            "payload": {"graceful": not args.no_graceful},
        }
    else:
        command = {
            "command": "list",
            "correlation_id": args.correlation_id or str(uuid.uuid4()),
            "user_id": args.user_id,
            "payload": {},
        }

    bus.enqueue_command(command)
    print("Enqueued command:")
    print(json.dumps(command, indent=2))
    print(f"\nWatch events: python scripts/send_conductor_command.py events")
    print(f"Or check Redis list: {EVENTS_KEY}")


if __name__ == "__main__":
    main()
