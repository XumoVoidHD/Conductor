"""Strategy request/response schemas."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import Field


class StrategyRegisterRequest(BaseModel):
    """Register a strategy file that already exists under ``strategies/``."""

    filename: str = Field(
        ...,
        min_length=1,
        max_length=128,
        examples=["running_ping", "running_ping.py", "ema_cross.py"],
        description="Module file name under strategies/ (with or without .py).",
    )


class StrategyGrantAccessRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, examples=["alice"])


class StrategyResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    module: str
    class_name: str
    config_class: str
    default_config: dict[str, Any]
    requires_market_data: bool
    is_global: bool
    created_by: str

    model_config = {"from_attributes": True}
