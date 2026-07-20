"""Password hashing and JWT helpers (login later)."""
from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from jose import JWTError
from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# Argon2 first (modern); bcrypt kept for future hash upgrades.
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    subject: str,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a JWT access token (reserved for login endpoint)."""
    settings = get_settings()
    expire = datetime.now(UTC) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT; returns None on failure."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        return None
