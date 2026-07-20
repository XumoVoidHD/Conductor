"""Authentication business logic."""
from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import create_access_token
from app.core.security import hash_password
from app.core.security import verify_password
from app.db.models.user import User
from app.db.models.user import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.auth import UserLoginRequest
from app.schemas.auth import UserRegisterRequest
from app.schemas.auth import UserResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self._users = UserRepository(db)

    def register(self, payload: UserRegisterRequest) -> User:
        username = payload.username.strip()
        email = payload.email.strip().lower()
        password = payload.password

        logger.info("Registration attempt username=%s email=%s", username, email)

        if self._users.get_by_username(username) is not None:
            logger.warning("Registration conflict: username already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists.",
            )

        if self._users.get_by_email(email) is not None:
            logger.warning("Registration conflict: email already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists.",
            )

        try:
            password_hash = hash_password(password)
            user = self._users.create(
                username=username,
                email=email,
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

    def login(self, payload: UserLoginRequest) -> TokenResponse:
        username = payload.username.strip()
        logger.info("Login attempt username=%s", username)

        user = self._users.get_by_username(username)
        # Same generic error whether user missing or password wrong (no user enumeration).
        if user is None or not user.is_active:
            logger.warning("Login failed: unknown or inactive user")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        if not verify_password(payload.password, user.password_hash):
            logger.warning("Login failed: bad password for username=%s", username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password.",
            )

        token = create_access_token(
            subject=str(user.id),
            extra_claims={"username": user.username, "role": user.role.value},
        )
        logger.info("Login ok id=%s username=%s", user.id, user.username)
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
