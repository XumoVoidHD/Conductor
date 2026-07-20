"""Strategy vault ORM models."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User

SYSTEM_CREATOR = "SYSTEM"


class Strategy(Base):
    """Runnable Nautilus strategy definition (global or user-owned)."""

    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(String(255), nullable=False)
    class_name: Mapped[str] = mapped_column(String(128), nullable=False)
    config_class: Mapped[str] = mapped_column(String(128), nullable=False)
    default_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    requires_market_data: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    # NULL creator = SYSTEM (global strategies only).
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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

    created_by: Mapped[User | None] = relationship(
        "User",
        back_populates="created_strategies",
        foreign_keys=[created_by_user_id],
    )
    access_grants: Mapped[list[StrategyAccess]] = relationship(
        back_populates="strategy",
        cascade="all, delete-orphan",
    )

    @property
    def creator_label(self) -> str:
        if self.created_by_user_id is None:
            return SYSTEM_CREATOR
        if self.created_by is not None:
            return self.created_by.username
        return SYSTEM_CREATOR

    def __repr__(self) -> str:
        return f"<Strategy slug={self.slug!r} global={self.is_global}>"


class StrategyAccess(Base):
    """Grants a user access to a non-global strategy owned by someone else."""

    __tablename__ = "strategy_access"
    __table_args__ = (
        UniqueConstraint("strategy_id", "user_id", name="uq_strategy_access_strategy_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("strategies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    strategy: Mapped[Strategy] = relationship(back_populates="access_grants")
    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="strategy_access_grants",
    )
    granted_by: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[granted_by_user_id],
    )
