"""add strategy source_url and source_path

Revision ID: 003_strategy_source
Revises: 002_create_strategies
Create Date: 2026-07-28

"""
from __future__ import annotations

from typing import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_strategy_source"
down_revision: Union[str, None] = "002_create_strategies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "strategies",
        sa.Column(
            "source_url",
            sa.String(length=512),
            server_default="local://strategies",
            nullable=False,
        ),
    )
    op.add_column(
        "strategies",
        sa.Column("source_path", sa.String(length=512), nullable=True),
    )
    # Backfill path from slug for existing rows
    op.execute(
        sa.text(
            "UPDATE strategies SET source_path = slug || '.py' "
            "WHERE source_path IS NULL",
        ),
    )
    op.alter_column("strategies", "source_path", nullable=False)


def downgrade() -> None:
    op.drop_column("strategies", "source_path")
    op.drop_column("strategies", "source_url")
