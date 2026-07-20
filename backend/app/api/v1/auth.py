"""Authentication routes."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.db.models.user import User
from app.schemas.auth import ErrorResponse
from app.schemas.auth import TokenResponse
from app.schemas.auth import UserLoginRequest
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
        "Create a new account. Password is hashed before storage. "
        "Username and email must be unique."
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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description=(
        "Authenticate with username and password. Returns a JWT access token. "
        "Send it as `Authorization: Bearer <token>` on protected routes."
    ),
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Invalid credentials",
        },
    },
)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return AuthService(db).login(payload)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current user",
    description="Return the authenticated user from the Bearer token.",
)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
