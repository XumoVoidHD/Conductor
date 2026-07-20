"""Authentication business logic."""
from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models.user import User
from app.db.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UserRegisterRequest

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def register(self, payload: UserRegisterRequest) -> User:
        logger.info(
            "Registration attempt username=%s email=%s",
            payload.username,
            payload.email,
        )

        if self._users.get_by_username(payload.username) is not None:
            logger.warning("Registration conflict: username already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists.",
            )

        if self._users.get_by_email(payload.email) is not None:
            logger.warning("Registration conflict: email already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists.",
            )

        try:
            password_hash = hash_password(payload.password)
            user = self._users.create(
                username=payload.username,
                email=str(payload.email).lower(),
                password_hash=password_hash,
                role=UserRole.USER,
                trading_nodes=2,
            )
        except Exception:
            logger.exception("Unexpected error during user registration")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to register user.",
            ) from None

        logger.info("User registered id=%s username=%s", user.id, user.username)
        return user
