"""Strategy vault database access."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.db.models.strategy import Strategy
from app.db.models.strategy import StrategyAccess


class StrategyRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_accessible_for_user(self, user_id: uuid.UUID) -> list[Strategy]:
        shared_ids = select(StrategyAccess.strategy_id).where(
            StrategyAccess.user_id == user_id,
        )
        stmt = (
            select(Strategy)
            .options(selectinload(Strategy.created_by))
            .where(
                or_(
                    Strategy.is_global.is_(True),
                    Strategy.created_by_user_id == user_id,
                    Strategy.id.in_(shared_ids),
                ),
            )
            .order_by(Strategy.is_global.desc(), Strategy.slug)
        )
        return list(self._db.scalars(stmt).all())

    def get_accessible_by_slug(
        self,
        user_id: uuid.UUID,
        slug: str,
    ) -> Strategy | None:
        shared_ids = select(StrategyAccess.strategy_id).where(
            StrategyAccess.user_id == user_id,
        )
        stmt = (
            select(Strategy)
            .options(selectinload(Strategy.created_by))
            .where(
                Strategy.slug == slug,
                or_(
                    Strategy.is_global.is_(True),
                    Strategy.created_by_user_id == user_id,
                    Strategy.id.in_(shared_ids),
                ),
            )
        )
        return self._db.scalars(stmt).first()

    def get_by_slug(self, slug: str) -> Strategy | None:
        stmt = (
            select(Strategy)
            .options(selectinload(Strategy.created_by))
            .where(Strategy.slug == slug)
        )
        return self._db.scalars(stmt).first()

    def create(
        self,
        *,
        slug: str,
        name: str,
        description: str | None,
        module: str,
        class_name: str,
        config_class: str,
        default_config: dict[str, Any],
        requires_market_data: bool,
        created_by_user_id: uuid.UUID | None,
        is_global: bool = False,
    ) -> Strategy:
        if is_global and created_by_user_id is not None:
            raise ValueError("Global (SYSTEM) strategies must have created_by_user_id=None.")
        if not is_global and created_by_user_id is None:
            raise ValueError("User-owned strategies require created_by_user_id.")

        strategy = Strategy(
            slug=slug,
            name=name,
            description=description,
            module=module,
            class_name=class_name,
            config_class=config_class,
            default_config=default_config,
            requires_market_data=requires_market_data,
            is_global=is_global,
            created_by_user_id=created_by_user_id,
        )
        self._db.add(strategy)
        self._db.commit()
        self._db.refresh(strategy)
        return strategy

    def grant_access(
        self,
        *,
        strategy: Strategy,
        user_id: uuid.UUID,
        granted_by_user_id: uuid.UUID,
    ) -> StrategyAccess:
        existing = self._db.scalars(
            select(StrategyAccess).where(
                StrategyAccess.strategy_id == strategy.id,
                StrategyAccess.user_id == user_id,
            ),
        ).first()
        if existing is not None:
            return existing

        grant = StrategyAccess(
            strategy_id=strategy.id,
            user_id=user_id,
            granted_by_user_id=granted_by_user_id,
        )
        self._db.add(grant)
        self._db.commit()
        self._db.refresh(grant)
        return grant

    @staticmethod
    def to_api_dict(strategy: Strategy) -> dict[str, Any]:
        return {
            "id": strategy.slug,
            "slug": strategy.slug,
            "name": strategy.name,
            "description": strategy.description,
            "module": strategy.module,
            "class_name": strategy.class_name,
            "config_class": strategy.config_class,
            "default_config": strategy.default_config or {},
            "requires_market_data": strategy.requires_market_data,
            "is_global": strategy.is_global,
            "created_by": strategy.creator_label,
        }
