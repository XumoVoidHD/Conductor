"""Persistence for trading_nodes rows."""
from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.trading_node import TradingNode


class TradingNodeRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def count_active_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(TradingNode)
            .where(
                TradingNode.user_id == user_id,
                TradingNode.deleted_at.is_(None),
            )
        )
        return int(self._db.scalar(stmt) or 0)

    def list_active_for_user(self, user_id: uuid.UUID) -> list[TradingNode]:
        stmt = (
            select(TradingNode)
            .where(
                TradingNode.user_id == user_id,
                TradingNode.deleted_at.is_(None),
            )
            .order_by(TradingNode.created_at.desc())
        )
        return list(self._db.scalars(stmt).all())

    def get_by_node_id(self, node_id: str, *, include_deleted: bool = False) -> TradingNode | None:
        stmt = select(TradingNode).where(TradingNode.node_id == node_id)
        row = self._db.scalar(stmt)
        if row is None:
            return None
        if not include_deleted and row.deleted_at is not None:
            return None
        return row

    def create(
        self,
        *,
        node_id: str,
        user_id: uuid.UUID,
        strategy_id: uuid.UUID | None,
        strategy_slug: str,
        strategy_name: str,
        strategy_module: str,
        strategy_class_name: str,
        strategy_config: dict[str, Any],
        broker_adapter: str,
        runtime: str,
        status: str,
        control_host: str | None = None,
        control_port: int | None = None,
        container_id: str | None = None,
        container_name: str | None = None,
        bootstrap_path: str | None = None,
    ) -> TradingNode:
        row = TradingNode(
            node_id=node_id,
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_slug=strategy_slug,
            strategy_name=strategy_name,
            strategy_module=strategy_module,
            strategy_class_name=strategy_class_name,
            strategy_config=strategy_config or {},
            broker_adapter=broker_adapter,
            runtime=runtime,
            status=status,
            control_host=control_host,
            control_port=control_port,
            container_id=container_id,
            container_name=container_name,
            bootstrap_path=bootstrap_path,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def update_status(
        self,
        node_id: str,
        *,
        status: str,
        control_host: str | None = None,
        control_port: int | None = None,
        container_id: str | None = None,
        container_name: str | None = None,
    ) -> TradingNode | None:
        row = self.get_by_node_id(node_id)
        if row is None:
            return None
        row.status = status
        if control_host is not None:
            row.control_host = control_host
        if control_port is not None:
            row.control_port = control_port
        if container_id is not None:
            row.container_id = container_id
        if container_name is not None:
            row.container_name = container_name
        if status.lower() == "stopped":
            row.stopped_at = datetime.now(timezone.utc)
        elif status.lower() in {"running", "ready", "initializing"}:
            row.stopped_at = None
        self._db.commit()
        self._db.refresh(row)
        return row

    def soft_delete(self, node_id: str) -> TradingNode | None:
        row = self.get_by_node_id(node_id)
        if row is None:
            return None
        now = datetime.now(timezone.utc)
        row.deleted_at = now
        row.status = "Deleted"
        row.stopped_at = now
        self._db.commit()
        self._db.refresh(row)
        return row

    @staticmethod
    def to_api_dict(row: TradingNode, *, live: dict[str, Any] | None = None) -> dict[str, Any]:
        status = (live or {}).get("status") or row.status
        ready = (live or {}).get("ready")
        if ready is None:
            ready = status.lower() in {"ready", "running"}
        alive = (live or {}).get("alive")
        if alive is None:
            alive = status.lower() not in {"stopped", "deleted"}
        return {
            "node_id": row.node_id,
            "status": status,
            "alive": bool(alive),
            "ready": bool(ready),
            "strategy": (live or {}).get("strategy"),
            "strategy_id": str(row.strategy_id) if row.strategy_id else None,
            "strategy_slug": row.strategy_slug,
            "strategy_name": row.strategy_name,
            "broker_adapter": row.broker_adapter,
            "deploy_status": (live or {}).get("deploy_status") or row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
