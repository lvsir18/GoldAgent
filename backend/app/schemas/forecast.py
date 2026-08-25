"""Forecast request/result schemas."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .common import SourceMetadata


class ForecastRequest(BaseModel):
    symbol: str = "AU0"
    horizon: int = Field(default=5, ge=1, le=30)
    model: Literal["linear", "ma", "exponential"] = "exponential"
    lookback: int | None = Field(default=None, ge=20, le=5000)


class ForecastMetrics(BaseModel):
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None
    direction_accuracy: float | None = None


class ForecastResult(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request: ForecastRequest
    current_price: float
    predicted_prices: list[float]
    predicted_change_pct: list[float]
    heuristic_score: float | None = None
    metrics: ForecastMetrics = Field(default_factory=ForecastMetrics)
    disclaimer: str = "Forecast is a model estimate, not a guaranteed future price."
    metadata: SourceMetadata

