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
from app.repositories.user_repository import UserRepository
from app.services.conductor_client import ConductorClient

logger = get_logger(__name__)


class DashboardService:
    def __init__(self, user: User, db: Session) -> None:
        self._settings = get_settings()
        self._conductor = ConductorClient()
        self._db = db
        self._strategies = StrategyRepository(db)
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
            "Deploying strategy_id=%s uri=%s user_id=%s created_by=%s",
            strategy_id,
            strategy.source_uri,
            self._user_id,
            strategy.creator_label,
        )
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
