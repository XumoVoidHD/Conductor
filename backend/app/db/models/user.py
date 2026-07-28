"""
Table: users

Platform accounts for Conductor.

Columns:
  id              UUID PK
  username        unique login name (also used as Conductor user_id)
  email           unique email
  password_hash   Argon2 hash
  role            USER | ADMIN  (ADMIN can register global SYSTEM strategies)
  trading_nodes   max concurrent trading nodes allowed
  is_active       soft disable
  created_at / updated_at
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean
from sqlalchemy import DateTime
from sqlalchemy import Enum
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.strategy import Strategy
    from app.db.models.strategy import StrategyAccess
    from app.db.models.trading_node import TradingNode


class UserRole(str, enum.Enum):
    USER = "USER"
    ADMIN = "ADMIN"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True),
        nullable=False,
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    trading_nodes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
        server_default="2",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    created_strategies: Mapped[list[Strategy]] = relationship(
        "Strategy",
        back_populates="created_by",
        foreign_keys="Strategy.created_by_user_id",
    )
    strategy_access_grants: Mapped[list[StrategyAccess]] = relationship(
        "StrategyAccess",
        back_populates="user",
        foreign_keys="StrategyAccess.user_id",
    )
    owned_trading_nodes: Mapped[list[TradingNode]] = relationship(
        "TradingNode",
        back_populates="user",
        foreign_keys="TradingNode.user_id",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
