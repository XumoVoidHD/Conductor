"""Auth request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.db.models.user import UserRole


class UserRegisterRequest(BaseModel):
    """Registration — minimal shape checks; uniqueness enforced in the service."""

    username: str = Field(..., min_length=1, max_length=64, examples=["vedansh"])
    email: str = Field(..., min_length=1, max_length=255, examples=["vedansh@example.com"])
    password: str = Field(..., min_length=1, max_length=128, examples=["Password@123"])


class UserLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, examples=["vedansh"])
    password: str = Field(..., min_length=1, examples=["Password@123"])


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    role: UserRole
    trading_nodes: int
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ErrorResponse(BaseModel):
    detail: str
