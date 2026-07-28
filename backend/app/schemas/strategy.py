"""Strategy request/response schemas."""
from __future__ import annotations

from typing import Any
from typing import Self

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator


class StrategyRegisterRequest(BaseModel):
    """
    Register a strategy artifact.

    Provide either:
    - ``filename`` — shorthand for local://strategies/<filename>
    - ``source_url`` + ``source_path`` — e.g. s3://bucket + users/a/foo.py
    """

    filename: str | None = Field(
        default=None,
        max_length=128,
        examples=["running_ping.py"],
        description="Local strategies/ filename (sets source_url=local://strategies).",
    )
    source_url: str | None = Field(
        default=None,
        max_length=512,
        examples=["local://strategies", "s3://my-bucket", "gs://my-bucket"],
        description="Base locator (scheme + bucket/root). Full URI = source_url/source_path.",
    )
    source_path: str | None = Field(
        default=None,
        max_length=512,
        examples=["running_ping.py", "users/alice/ema_cross.py"],
        description="Path/key within source_url.",
    )

    @model_validator(mode="after")
    def require_filename_or_source_parts(self) -> Self:
        has_file = bool(self.filename and self.filename.strip())
        has_parts = bool(
            self.source_url
            and self.source_url.strip()
            and self.source_path
            and self.source_path.strip(),
        )
        if has_file == has_parts:
            raise ValueError(
                "Provide either filename (local strategies/) "
                "or both source_url and source_path.",
            )
        return self


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
    source_url: str
    source_path: str
    source_uri: str

    model_config = {"from_attributes": True}
