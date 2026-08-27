"""Dashboard / Conductor control business logic."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.user import User
from app.repositories.strategy_repository import StrategyRepository
from app.repositories.trading_node_repository import TradingNodeRepository
from app.repositories.user_repository import UserRepository
from app.services.conductor_client import ConductorClient

logger = get_logger(__name__)


class DashboardService:
    def __init__(self, user: User, db: Session) -> None:
        self._settings = get_settings()
        self._conductor = ConductorClient()
        self._db = db
        self._strategies = StrategyRepository(db)
        self._nodes = TradingNodeRepository(db)
        # Conductor multi-tenancy key = authenticated username (never trust client body).
        self._user_id = user.username
        self._user = user

    def list_strategies(self) -> list[dict[str, Any]]:
        rows = self._strategies.list_accessible_for_user(self._user.id)
        return [StrategyRepository.to_api_dict(row) for row in rows]

    def register_strategy_from_file(self, filename: str) -> dict[str, Any]:
        from shared.artifacts import ArtifactLocation

        return self.register_strategy_from_location(
            ArtifactLocation.local_strategies(filename),
        )

    def register_strategy_from_location(self, location) -> dict[str, Any]:
        """
        Register a strategy from ``source_url`` + ``source_path``.

        - ADMIN → global SYSTEM strategy (created_by_user_id=NULL, is_global=True)
        - USER  → owned by this user (is_global=False)

        Artifact is materialized (local open / S3 / GCS download) for discovery.
        """
        from app.db.models.user import UserRole
        from app.services.strategy_discovery import discover_strategy_from_location
        from shared.artifacts import ArtifactLocation

        if not isinstance(location, ArtifactLocation):
            location = ArtifactLocation.from_parts(
                location.source_url,
                location.source_path,
            )

        try:
            discovered = discover_strategy_from_location(location)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        if self._strategies.get_by_slug(discovered.slug) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Strategy slug '{discovered.slug}' already registered.",
            )

        as_system = self._user.role == UserRole.ADMIN
        strategy = self._strategies.create(
            slug=discovered.slug,
            name=discovered.name,
            description=discovered.description,
            module=discovered.module,
            class_name=discovered.class_name,
            config_class=discovered.config_class,
            default_config=discovered.default_config,
            requires_market_data=discovered.requires_market_data,
            created_by_user_id=None if as_system else self._user.id,
            is_global=as_system,
            source_url=discovered.source_url,
            source_path=discovered.source_path,
        )
        logger.info(
            "Registered strategy slug=%s uri=%s as %s by user=%s",
            discovered.slug,
            discovered.source_uri,
            "SYSTEM" if as_system else self._user.username,
            self._user.username,
        )
        return StrategyRepository.to_api_dict(strategy)

    def grant_strategy_access(self, slug: str, username: str) -> dict[str, Any]:
        strategy = self._strategies.get_by_slug(slug)
        if strategy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown strategy '{slug}'.",
            )
        if strategy.is_global:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Global strategies are already available to all users.",
            )
        if strategy.created_by_user_id != self._user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the strategy owner can grant access.",
            )

        target = UserRepository(self._db).get_by_username(username)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found.",
            )
        if target.id == self._user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Owner already has access.",
            )

        self._strategies.grant_access(
            strategy=strategy,
            user_id=target.id,
            granted_by_user_id=self._user.id,
        )
        return {
            "slug": strategy.slug,
            "granted_to": target.username,
            "granted_by": self._user.username,
        }

    def conductor_status(self) -> dict[str, Any]:
        return {
            "redis_ok": self._conductor.ping(),
            "user_id": self._user_id,
        }

    def _live_nodes_by_id(self) -> dict[str, dict[str, Any]]:
        """Best-effort live probe from Conductor; empty if Conductor is down."""
        try:
            event = self._conductor.enqueue_and_wait(
                {
                    "command": "list",
                    "user_id": self._user_id,
                    "payload": {},
                },
            )
        except Exception as exc:  # noqa: BLE001 — list should still work from DB
            logger.warning("Conductor list failed during node merge: %s", exc)
            return {}
        if event.get("status") == "error":
            logger.warning("Conductor list error: %s", event.get("message"))
            return {}
        nodes = (event.get("data") or {}).get("nodes", [])
        return {str(n["node_id"]): n for n in nodes if n.get("node_id")}

    def list_nodes(self) -> dict[str, Any]:
        rows = self._nodes.list_active_for_user(self._user.id)
        live_by_id = self._live_nodes_by_id()

        nodes: list[dict[str, Any]] = []
        for row in rows:
            live = live_by_id.get(row.node_id)
            if live and live.get("status") and live["status"] != row.status:
                updated = self._nodes.update_status(
                    row.node_id,
                    status=str(live["status"]),
                    control_host=live.get("control_host"),
                    control_port=live.get("control_port"),
                    container_id=live.get("container_id"),
                )
                if updated is not None:
                    row = updated
            nodes.append(TradingNodeRepository.to_api_dict(row, live=live))

        return {
            "status": "ok",
            "message": f"{len(nodes)} node(s)",
            "data": {
                "nodes": nodes,
                "node_count": len(nodes),
                "max_trading_nodes": self._user.trading_nodes,
            },
        }

    def _assert_node_quota(self) -> None:
        """Stopped nodes still count — only delete frees a slot."""
        used = self._nodes.count_active_for_user(self._user.id)
        limit = int(self._user.trading_nodes)
        if used >= limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Trading node limit reached ({used}/{limit}). "
                    "Delete a node before deploying another. "
                    "Stopping a node does not free a slot."
                ),
            )

    def deploy_strategy(
        self,
        strategy_id: str,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._assert_node_quota()

        strategy = self._strategies.get_accessible_by_slug(self._user.id, strategy_id)
        if strategy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown or inaccessible strategy '{strategy_id}'",
            )

        api_key, api_secret = self._settings.bybit_credentials()
        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Bybit credentials missing in .env "
                    "(BYBIT_TESTNET_API_KEY / BYBIT_TESTNET_API_SECRET)."
                ),
            )

        strategy_config = dict(strategy.default_config or {})
        if config_overrides:
            strategy_config.update(config_overrides)

        instrument_id = self._settings.bybit_instrument_id
        if "instrument_id" not in strategy_config and strategy.requires_market_data:
            strategy_config["instrument_id"] = instrument_id

        command = {
            "command": "deploy",
            "user_id": self._user_id,
            "payload": {
                "max_trading_nodes": self._user.trading_nodes,
                "broker": {
                    "adapter": "bybit",
                    "config": {
                        "api_key": api_key,
                        "api_secret": api_secret,
                        "environment": self._settings.bybit_environment,
                        "product_types": [self._settings.bybit_product_type],
                        "instrument_ids": [instrument_id],
                    },
                },
                "strategy": {
                    "module": strategy.module,
                    "class_name": strategy.class_name,
                    "config_class": strategy.config_class,
                    "config": strategy_config,
                    "source_url": strategy.source_url,
                    "source_path": strategy.source_path,
                },
            },
        }
        logger.info(
            "Deploying strategy_id=%s uri=%s user_id=%s created_by=%s quota=%s",
            strategy_id,
            strategy.source_uri,
            self._user_id,
            strategy.creator_label,
            self._user.trading_nodes,
        )
        event = self._conductor.enqueue_and_wait(command)
        self._raise_if_error(event)

        data = event.get("data") or {}
        node_id = str(event.get("node_id") or "")
        if node_id:
            container_name = (
                f"conductor-{node_id}" if data.get("runtime") == "docker" else None
            )
            self._nodes.create(
                node_id=node_id,
                user_id=self._user.id,
                strategy_id=strategy.id,
                strategy_slug=strategy.slug,
                strategy_name=strategy.name,
                strategy_module=strategy.module,
                strategy_class_name=strategy.class_name,
                strategy_config=strategy_config,
                broker_adapter=str(data.get("broker_adapter") or "bybit"),
                runtime=str(data.get("runtime") or "docker"),
                status=str(data.get("status") or "Initializing"),
                control_host=data.get("control_host"),
                control_port=data.get("control_port"),
                container_id=data.get("container_id"),
                container_name=container_name,
                bootstrap_path=data.get("bootstrap_path"),
            )
        return event

    def node_action(self, action: str, node_id: str) -> dict[str, Any]:
        allowed = {"run", "stop", "status", "restart", "delete", "halt", "reset"}
        if action not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action '{action}'",
            )

        owned = self._nodes.get_by_node_id(node_id)
        if owned is None or owned.user_id != self._user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_id}' not found for your account.",
            )

        command: dict[str, Any] = {
            "command": action,
            "user_id": self._user_id,
            "node_id": node_id,
            "payload": {},
        }
        if action in {"stop", "delete"}:
            command["payload"] = {"graceful": True}

        event = self._conductor.enqueue_and_wait(command)
        if event.get("status") == "error":
            message = str(event.get("message") or "Conductor returned an error")
            if self._is_node_gone_message(message, node_id):
                self._nodes.soft_delete(node_id)
                used = self._nodes.count_active_for_user(self._user.id)
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail={
                        "code": "node_gone",
                        "message": (
                            f"Node '{node_id}' is gone "
                            "(container missing or unknown to Conductor) "
                            "and was removed from your list. "
                            f"Active nodes: {used}/{self._user.trading_nodes}."
                        ),
                        "node_id": node_id,
                        "node_count": used,
                        "max_trading_nodes": self._user.trading_nodes,
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=message,
            )

        data = event.get("data") or {}
        if action == "delete":
            self._nodes.soft_delete(node_id)
        else:
            status_value = data.get("status")
            if not status_value and action == "stop":
                status_value = "Stopped"
            if not status_value and action == "run":
                status_value = "Running"
            if not status_value and action == "restart":
                status_value = "Initializing"
            if status_value:
                self._nodes.update_status(
                    node_id,
                    status=str(status_value),
                    control_host=data.get("control_host"),
                    control_port=data.get("control_port"),
                    container_id=data.get("container_id"),
                )
        return event

    def get_node_snapshot(self, node_ref: str) -> dict[str, Any]:
        """
        Pull a full Nautilus snapshot from a live trading node.

        Resolves ``node_ref`` as node_id or Docker container name, checks
        ownership, then talks to the node control TCP socket directly
        (observe path — not via Conductor).

        If the node process/container is stopped (TCP unreachable), returns an
        offline snapshot built from the DB record so callers can still inspect
        strategy identity and last known status.
        """
        from datetime import datetime
        from datetime import timezone

        from app.services.node_control_client import fetch_node_snapshot

        row = self._nodes.get_by_ref(node_ref)
        if row is None or row.user_id != self._user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Node '{node_ref}' not found for your account.",
            )

        host = row.control_host or row.container_name or f"conductor-{row.node_id}"
        port = int(row.control_port or 9000)
        container_name = row.container_name or f"conductor-{row.node_id}"

        try:
            snapshot = fetch_node_snapshot(host, port)
            reachable = True
        except ConnectionError:
            reachable = False
            snapshot = self._offline_snapshot(row, host=host, port=port)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

        if reachable:
            strategy_state = (snapshot.get("strategy") or {}).get("state")
            if strategy_state == "running":
                self._nodes.update_status(row.node_id, status="Running")
            elif strategy_state in {"stopped", "missing"}:
                health = snapshot.get("health") or {}
                if health.get("node_running"):
                    self._nodes.update_status(row.node_id, status="Ready")

        return {
            "node_id": row.node_id,
            "container_name": container_name,
            "strategy_slug": row.strategy_slug,
            "strategy_name": row.strategy_name,
            "reachable": reachable,
            "queried_via": {"host": host, "port": port},
            "snapshot": snapshot,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_traders(self) -> dict[str, Any]:
        """
        Phase-1 observe: batch lightweight trader summaries for the user's nodes.

        Pulls TCP ``summary`` (or snapshot fallback) per node with bounded
        concurrency. Offline nodes return a DB-backed stub. Frontend filters
        locally — this always returns the full set for the user.
        """
        from concurrent.futures import ThreadPoolExecutor
        from concurrent.futures import as_completed
        from datetime import datetime
        from datetime import timezone

        from app.services.node_control_client import fetch_node_summary

        rows = self._nodes.list_active_for_user(self._user.id)
        if not rows:
            return {
                "status": "ok",
                "message": "0 trader(s)",
                "traders": [],
                "trader_count": 0,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }

        def _one(row: Any) -> dict[str, Any]:
            host = row.control_host or row.container_name or f"conductor-{row.node_id}"
            port = int(row.control_port or 9000)
            base = {
                "node_id": row.node_id,
                "trader_id": None,
                "strategy_slug": row.strategy_slug,
                "strategy_name": row.strategy_name,
                "broker_adapter": row.broker_adapter,
                "db_status": row.status,
                "reachable": False,
                "strategy_state": None,
                "positions_open": 0,
                "orders_open": 0,
                "queried_via": {"host": host, "port": port},
            }
            try:
                summary = fetch_node_summary(host, port, timeout_sec=8.0)
                strategy = summary.get("strategy") or {}
                health = summary.get("health") or {}
                return {
                    **base,
                    "trader_id": summary.get("trader_id"),
                    "reachable": True,
                    "strategy_state": strategy.get("state") or health.get("strategy_state"),
                    "positions_open": int(summary.get("positions_open") or 0),
                    "orders_open": int(summary.get("orders_open") or 0),
                    "health": health,
                    "captured_at": summary.get("captured_at"),
                }
            except ConnectionError:
                return {
                    **base,
                    "trader_id": f"CONDUCTOR-{row.node_id.upper()}",
                    "strategy_state": "offline",
                    "offline_reason": f"unreachable at {host}:{port}",
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                }
            except RuntimeError as exc:
                return {
                    **base,
                    "trader_id": f"CONDUCTOR-{row.node_id.upper()}",
                    "strategy_state": "error",
                    "offline_reason": str(exc),
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                }

        traders: list[dict[str, Any]] = []
        # Small quotas → 3 concurrent TCP probes is enough
        with ThreadPoolExecutor(max_workers=min(3, len(rows))) as pool:
            futures = {pool.submit(_one, row): row.node_id for row in rows}
            by_id: dict[str, dict[str, Any]] = {}
            for fut in as_completed(futures):
                by_id[futures[fut]] = fut.result()
        # Stable order matching DB list
        traders = [by_id[row.node_id] for row in rows if row.node_id in by_id]

        return {
            "status": "ok",
            "message": f"{len(traders)} trader(s)",
            "traders": traders,
            "trader_count": len(traders),
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _offline_snapshot(row: Any, *, host: str, port: int) -> dict[str, Any]:
        """DB-backed snapshot when the trading node control socket is down."""
        from datetime import datetime
        from datetime import timezone

        status_label = row.status or "Stopped"
        return {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "source": "database",
            "offline": True,
            "offline_reason": (
                f"Trading node not reachable at {host}:{port} "
                f"(last known status: {status_label}). "
                "Start/restart the node for a live Nautilus snapshot."
            ),
            "node": {
                "node_id": row.node_id,
                "user_id": None,
                "trader_id": None,
                "is_running": False,
                "shutting_down": False,
            },
            "health": {
                "node_running": False,
                "reachable": False,
                "shutting_down": False,
                "strategy_state": "unknown",
                "db_status": status_label,
                "stopped_at": row.stopped_at.isoformat() if row.stopped_at else None,
                "kernel_loop_alive": False,
                "data_engine_running": False,
                "exec_engine_running": False,
                "risk_engine_running": False,
            },
            "strategy": {
                "id": None,
                "state": "offline",
                "is_running": False,
                "is_stopped": True,
                "slug": row.strategy_slug,
                "name": row.strategy_name,
                "module": row.strategy_module,
                "class_name": row.strategy_class_name,
                "config": row.strategy_config or {},
            },
            "indicators": [],
            "positions": {"open": [], "closed": [], "open_count": 0, "closed_count": 0},
            "orders": {
                "open": [],
                "closed": [],
                "inflight": [],
                "open_count": 0,
                "closed_count": 0,
            },
            "fills": [],
            "balances": [],
            "portfolio": {},
            "market_data_subscriptions": {
                "bars": [],
                "quotes": [],
                "trades": [],
                "instruments": [],
                "other": [],
            },
            "instruments": [],
            "risk": {},
            "logs": [],
            "errors": [
                f"offline: control socket {host}:{port} unreachable",
            ],
            "broker_adapter": row.broker_adapter,
        }

    @staticmethod
    def _is_node_gone_message(message: str, node_id: str) -> bool:
        """Conductor/registry or Docker no longer knows this node."""
        m = message.lower()
        nid = node_id.lower()
        if f"node {nid} not found" in m:
            return True
        if "container" in m and "not found" in m:
            return True
        if "redeploy the node" in m:
            return True
        return False

    @staticmethod
    def _raise_if_error(event: dict[str, Any]) -> None:
        if event.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=event.get("message") or "Conductor returned an error",
            )
