"""WebSocket auth helpers (browser cannot set Authorization on WS handshake)."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models.user import User
from app.repositories.user_repository import UserRepository


def user_from_access_token(token: str, db: Session) -> User:
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
        )

    payload = decode_access_token(token.strip())
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        )

    try:
        user_id = uuid.UUID(str(sub))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
        ) from exc

    user = UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )
    return user
