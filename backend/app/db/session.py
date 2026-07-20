"""Model registry for Alembic metadata discovery."""
from __future__ import annotations

from app.db.base import Base
from app.db.models.user import User

__all__ = ["Base", "User"]
