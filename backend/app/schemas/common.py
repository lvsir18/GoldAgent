"""Cross-cutting API and provenance schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class SourceMetadata(BaseModel):
    source: str
    source_type: Literal["direct", "derived", "cache", "simulation"]
    is_derived: bool = False
    is_cached: bool = False
    is_stale: bool = False
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_start: datetime | None = None
    data_end: datetime | None = None
    currency: str
    market: str
    symbol: str
    reference: str | None = None


class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: ApiError | None = None

