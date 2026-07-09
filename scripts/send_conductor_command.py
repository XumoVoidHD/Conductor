#!/usr/bin/env python3
"""
Send commands to Conductor Node via Redis (temporary — API will replace this).

The deploy command must be complete: broker.adapter + full broker.config + strategy.
Conductor does not allocate broker credentials.

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


def _strategy_block(args: argparse.Namespace) -> dict:
    return {
        "module": args.strategy_module or "strategies.running_ping",
        "class_name": args.strategy_class or "RunningPing",
        "config_class": args.strategy_config_class or "RunningPingConfig",
    }


def _bybit_credentials(environment: str) -> tuple[str, str]:
    env = environment.lower()
    if env == "testnet":
        api_key = os.getenv("BYBIT_TESTNET_API_KEY") or os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_TESTNET_API_SECRET") or os.getenv("BYBIT_API_SECRET")
    elif env == "demo":
        api_key = os.getenv("BYBIT_DEMO_API_KEY") or os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_DEMO_API_SECRET") or os.getenv("BYBIT_API_SECRET")
    else:
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
    return api_key or "", api_secret or ""


def _build_bybit_deploy_payload(args: argparse.Namespace) -> dict:
    environment = args.bybit_environment or os.getenv("BYBIT_ENVIRONMENT", "testnet")
    api_key = args.bybit_api_key or _bybit_credentials(environment)[0]
    api_secret = args.bybit_api_secret or _bybit_credentials(environment)[1]
    if not api_key or not api_secret:
        raise SystemExit(
            "Bybit API credentials required "
            "(--bybit-api-key/--bybit-api-secret or BYBIT_TESTNET_API_KEY/SECRET in .env)",
        )

    product_type = args.bybit_product_type or os.getenv("BYBIT_PRODUCT_TYPE", "linear")
    symbol = args.bybit_symbol or os.getenv("BYBIT_SYMBOL", "BTCUSDT")
    instrument_id = args.bybit_instrument_id or os.getenv(
        "BYBIT_INSTRUMENT_ID",
        f"{symbol}-{product_type.upper()}.BYBIT",
    )

    payload: dict = {
        "broker": {
            "adapter": "bybit",
            "config": {
                "api_key": api_key,
                "api_secret": api_secret,
                "environment": environment,
                "product_types": [product_type],
                "instrument_ids": [instrument_id],
            },
        },
        "strategy": _strategy_block(args),
    }
    if args.control_port is not None:
        payload["control_port"] = args.control_port
    return payload


def _build_ibkr_deploy_payload(args: argparse.Namespace) -> dict:
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
        "strategy": _strategy_block(args),
    }
    if args.control_port is not None:
        payload["control_port"] = args.control_port
    return payload


def _build_deploy_command(args: argparse.Namespace) -> dict:
    broker = (args.broker or os.getenv("BROKER_ADAPTER", "bybit")).strip().lower()
    if broker == "bybit":
        payload = _build_bybit_deploy_payload(args)
    elif broker in ("interactive_brokers", "ibkr"):
        payload = _build_ibkr_deploy_payload(args)
    else:
        raise SystemExit(f"unsupported broker '{broker}' (use bybit or interactive_brokers)")

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
    deploy.add_argument("--broker", choices=["bybit", "interactive_brokers", "ibkr"])
    deploy.add_argument("--control-port", type=int)
    deploy.add_argument("--strategy-module")
    deploy.add_argument("--strategy-class")
    deploy.add_argument("--strategy-config-class")
    # Bybit
    deploy.add_argument("--bybit-api-key")
    deploy.add_argument("--bybit-api-secret")
    deploy.add_argument("--bybit-environment", choices=["testnet", "mainnet", "demo"])
    deploy.add_argument("--bybit-product-type", choices=["spot", "linear", "inverse", "option"])
    deploy.add_argument("--bybit-symbol", help="e.g. BTCUSDT (used to build instrument id)")
    deploy.add_argument("--bybit-instrument-id", help="e.g. BTCUSDT-LINEAR.BYBIT")
    # IBKR (optional — kept for later)
    deploy.add_argument("--account-id")
    deploy.add_argument("--ib-host")
    deploy.add_argument("--ib-port", type=int)
    deploy.add_argument("--ib-client-id", type=int)
    deploy.add_argument("--ib-symbol")
    deploy.add_argument("--ib-exchange")
    deploy.add_argument("--ib-currency")

    stop = sub.add_parser("stop", help="Stop a trading node")
    stop.add_argument("--user-id", required=True)
    stop.add_argument("--node-id", required=True)
    stop.add_argument("--correlation-id")
    stop.add_argument("--no-graceful", action="store_true")

    list_cmd = sub.add_parser("list", help="List nodes for a user")
    list_cmd.add_argument("--user-id", required=True)
    list_cmd.add_argument("--correlation-id")

    run_cmd = sub.add_parser("run", help="Start strategy on a deployed node")
    run_cmd.add_argument("--user-id", required=True)
    run_cmd.add_argument("--node-id", required=True)
    run_cmd.add_argument("--correlation-id")

    halt_cmd = sub.add_parser("halt", help="Stop strategy on a deployed node")
    halt_cmd.add_argument("--user-id", required=True)
    halt_cmd.add_argument("--node-id", required=True)
    halt_cmd.add_argument("--correlation-id")

    status_cmd = sub.add_parser("status", help="Strategy status on a deployed node")
    status_cmd.add_argument("--user-id", required=True)
    status_cmd.add_argument("--node-id", required=True)
    status_cmd.add_argument("--correlation-id")

    reset_cmd = sub.add_parser("reset", help="Reset strategy state (must be halted)")
    reset_cmd.add_argument("--user-id", required=True)
    reset_cmd.add_argument("--node-id", required=True)
    reset_cmd.add_argument("--correlation-id")

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
    elif args.action in ("run", "halt", "status", "reset"):
        command = {
            "command": args.action,
            "correlation_id": args.correlation_id or str(uuid.uuid4()),
            "user_id": args.user_id,
            "node_id": args.node_id,
            "payload": {},
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
