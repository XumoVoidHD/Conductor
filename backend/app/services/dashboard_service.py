"""Dashboard / Conductor control business logic."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi import status

from app.catalog.strategies import get_strategy
from app.catalog.strategies import list_strategies
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models.user import User
from app.services.conductor_client import ConductorClient

logger = get_logger(__name__)


class DashboardService:
    def __init__(self, user: User) -> None:
        self._settings = get_settings()
        self._conductor = ConductorClient()
        # Conductor multi-tenancy key = authenticated username (never trust client body).
        self._user_id = user.username

    def list_strategies(self) -> list[dict[str, Any]]:
        return list_strategies()

    def conductor_status(self) -> dict[str, Any]:
        return {
            "redis_ok": self._conductor.ping(),
            "user_id": self._user_id,
        }

    def list_nodes(self) -> dict[str, Any]:
        event = self._conductor.enqueue_and_wait(
            {
                "command": "list",
                "user_id": self._user_id,
                "payload": {},
            },
        )
        self._raise_if_error(event)
        return event

    def deploy_strategy(
        self,
        strategy_id: str,
        *,
        config_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strategy = get_strategy(strategy_id)
        if strategy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unknown strategy '{strategy_id}'",
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

        strategy_config = dict(strategy["default_config"])
        if config_overrides:
            strategy_config.update(config_overrides)

        instrument_id = self._settings.bybit_instrument_id
        if "instrument_id" not in strategy_config and strategy["requires_market_data"]:
            strategy_config["instrument_id"] = instrument_id

        command = {
            "command": "deploy",
            "user_id": self._user_id,
            "payload": {
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
                    "module": strategy["module"],
                    "class_name": strategy["class_name"],
                    "config_class": strategy["config_class"],
                    "config": strategy_config,
                },
            },
        }
        logger.info("Deploying strategy_id=%s user_id=%s", strategy_id, self._user_id)
        event = self._conductor.enqueue_and_wait(command)
        self._raise_if_error(event)
        return event

    def node_action(self, action: str, node_id: str) -> dict[str, Any]:
        if action not in {"run", "halt", "status", "reset", "stop"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported action '{action}'",
            )
        command: dict[str, Any] = {
            "command": action,
            "user_id": self._user_id,
            "node_id": node_id,
            "payload": {},
        }
        if action == "stop":
            command["payload"] = {"graceful": True}

        event = self._conductor.enqueue_and_wait(command)
        self._raise_if_error(event)
        return event

    @staticmethod
    def _raise_if_error(event: dict[str, Any]) -> None:
        if event.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=event.get("message") or "Conductor returned an error",
            )
