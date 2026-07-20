"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import ErrorResponse
from app.schemas.auth import UserRegisterRequest
from app.schemas.auth import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Create a new account with username, email, and password. "
        "Passwords are hashed before storage. Default role is USER "
        "with trading_nodes=2."
    ),
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ErrorResponse,
            "description": "Username or email already exists",
        },
    },
)
def register(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    service = AuthService(db)
    user = service.register(payload)
    return UserResponse.model_validate(user)
