"""create trading_nodes table

Revision ID: 004_trading_nodes
Revises: 003_strategy_source
Create Date: 2026-07-29

"""
from __future__ import annotations

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_trading_nodes"
down_revision: Union[str, None] = "003_strategy_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("strategy_id", sa.UUID(), nullable=True),
        sa.Column("strategy_slug", sa.String(length=64), nullable=False),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_module", sa.String(length=255), nullable=False),
        sa.Column("strategy_class_name", sa.String(length=128), nullable=False),
        sa.Column(
            "strategy_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("broker_adapter", sa.String(length=64), nullable=False),
        sa.Column("runtime", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("control_host", sa.String(length=255), nullable=True),
        sa.Column("control_port", sa.Integer(), nullable=True),
        sa.Column("container_id", sa.String(length=128), nullable=True),
        sa.Column("container_name", sa.String(length=128), nullable=True),
        sa.Column("bootstrap_path", sa.String(length=512), nullable=True),
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
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trading_nodes_node_id"), "trading_nodes", ["node_id"], unique=True)
    op.create_index(op.f("ix_trading_nodes_user_id"), "trading_nodes", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_trading_nodes_strategy_id"),
        "trading_nodes",
        ["strategy_id"],
        unique=False,
    )
    op.create_index(
        "ix_trading_nodes_user_active",
        "trading_nodes",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_trading_nodes_user_active", table_name="trading_nodes")
    op.drop_index(op.f("ix_trading_nodes_strategy_id"), table_name="trading_nodes")
    op.drop_index(op.f("ix_trading_nodes_user_id"), table_name="trading_nodes")
    op.drop_index(op.f("ix_trading_nodes_node_id"), table_name="trading_nodes")
    op.drop_table("trading_nodes")
