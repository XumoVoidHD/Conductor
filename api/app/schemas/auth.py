"""Auth request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field

from app.db.models.user import UserRole


class UserRegisterRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="3–64 chars; letters, numbers, underscore, hyphen, dot",
        examples=["vedansh"],
    )
    email: EmailStr = Field(..., examples=["vedansh@example.com"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Minimum 8 characters",
        examples=["Password@123"],
    )


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: EmailStr
    role: UserRole
    trading_nodes: int
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ErrorResponse(BaseModel):
    detail: str
