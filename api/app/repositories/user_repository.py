"""User database access."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.user import UserRole


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._db.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username)
        return self._db.scalars(stmt).first()

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return self._db.scalars(stmt).first()

    def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.USER,
        trading_nodes: int = 2,
    ) -> User:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            trading_nodes=trading_nodes,
            is_active=True,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user
