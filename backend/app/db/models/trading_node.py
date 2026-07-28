"""
Table: trading_nodes

Durable records for deployed trading nodes (survive Conductor restarts).
Deleted nodes keep a row with deleted_at set; quota/list ignore those.

Note: users.trading_nodes is the quota int — this table is the node registry.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.strategy import Strategy
    from app.db.models.user import User


class TradingNode(Base):
    __tablename__ = "trading_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    node_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    strategy_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_module: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy_class_name: Mapped[str] = mapped_column(String(128), nullable=False)
    strategy_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    broker_adapter: Mapped[str] = mapped_column(String(64), nullable=False, default="bybit")
    runtime: Mapped[str] = mapped_column(String(32), nullable=False, default="docker")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Initializing")
    control_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    control_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    container_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bootstrap_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship("User", back_populates="owned_trading_nodes")
    strategy: Mapped[Strategy | None] = relationship("Strategy")

    def __repr__(self) -> str:
        return (
            f"<TradingNode node_id={self.node_id!r} "
            f"user_id={self.user_id} status={self.status!r}>"
        )
