"""Market-data boundary schemas."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, Field

from .common import SourceMetadata


class MarketPoint(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0
    is_provisional: bool = False


class MarketHistory(BaseModel):
    points: list[MarketPoint]
    metadata: SourceMetadata


class MarketSummary(BaseModel):
    price: float
    previous_close: float | None = None
    previous_settlement: float | None = None
    trading_date: date | None = None
    quote_time: time | None = None
    is_realtime: bool = False
    change_basis: str = "previous_close"
    change_1d_pct: float | None = None
    change_1w_pct: float | None = None
    change_1m_pct: float | None = None
    usd_cny: float | None = None
    metadata: SourceMetadata


class TechnicalSnapshot(BaseModel):
    timestamp: datetime
    close: float
    ma: dict[str, float | None] = Field(default_factory=dict)
    rsi: float | None = None
    macd: float | None = None
    macd_signal: float | None = None
    atr: float | None = None
    volatility: float | None = None
    trend: str
    support: float | None = None
    resistance: float | None = None
    metadata: SourceMetadata
