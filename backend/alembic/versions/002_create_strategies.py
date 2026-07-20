"""create strategies and strategy_access tables

Revision ID: 002_create_strategies
Revises: 001_create_users
Create Date: 2026-07-20

"""
from __future__ import annotations

import uuid
from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.catalog.strategies import GLOBAL_STRATEGY_SEEDS

revision: str = "002_create_strategies"
down_revision: Union[str, None] = "001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module", sa.String(length=255), nullable=False),
        sa.Column("class_name", sa.String(length=128), nullable=False),
        sa.Column("config_class", sa.String(length=128), nullable=False),
        sa.Column(
            "default_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "requires_market_data",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("is_global", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_strategies_created_by_user_id"), "strategies", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_strategies_slug"), "strategies", ["slug"], unique=True)

    op.create_table(
        "strategy_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("strategy_id", "user_id", name="uq_strategy_access_strategy_user"),
    )
    op.create_index(op.f("ix_strategy_access_strategy_id"), "strategy_access", ["strategy_id"], unique=False)
    op.create_index(op.f("ix_strategy_access_user_id"), "strategy_access", ["user_id"], unique=False)

    strategies = sa.table(
        "strategies",
        sa.column("id", sa.UUID()),
        sa.column("slug", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("module", sa.String()),
        sa.column("class_name", sa.String()),
        sa.column("config_class", sa.String()),
        sa.column("default_config", postgresql.JSONB()),
        sa.column("requires_market_data", sa.Boolean()),
        sa.column("is_global", sa.Boolean()),
        sa.column("created_by_user_id", sa.UUID()),
    )
    op.bulk_insert(
        strategies,
        [
            {
                "id": uuid.uuid4(),
                "slug": seed["slug"],
                "name": seed["name"],
                "description": seed.get("description"),
                "module": seed["module"],
                "class_name": seed["class_name"],
                "config_class": seed["config_class"],
                "default_config": seed.get("default_config") or {},
                "requires_market_data": seed.get("requires_market_data", False),
                "is_global": True,
                "created_by_user_id": None,
            }
            for seed in GLOBAL_STRATEGY_SEEDS
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_strategy_access_user_id"), table_name="strategy_access")
    op.drop_index(op.f("ix_strategy_access_strategy_id"), table_name="strategy_access")
    op.drop_table("strategy_access")
    op.drop_index(op.f("ix_strategies_slug"), table_name="strategies")
    op.drop_index(op.f("ix_strategies_created_by_user_id"), table_name="strategies")
    op.drop_table("strategies")
