"""Pydantic input schemas for Agent-visible tools."""

from typing import Literal

from pydantic import BaseModel, Field


class MarketQuery(BaseModel):
    symbol: str = Field(default="AU0", min_length=1, max_length=20)
    market: Literal["CN", "INTL"] = "CN"
    period: str = Field(default="3y", pattern=r"^(\d+[ymd]|max|all)$")


class MarketHistoryQuery(MarketQuery):
    limit: int = Field(default=120, ge=5, le=500)


class TechnicalQuery(MarketQuery):
    pass


class NewsQuery(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    max_results: int = Field(default=10, ge=1, le=20)


class ForecastToolQuery(MarketQuery):
    horizon: int = Field(default=5, ge=1, le=30)
    model: Literal["linear", "ma", "exponential"] = "exponential"
    lookback: int | None = Field(default=None, ge=20, le=5000)


class PortfolioToolQuery(BaseModel):
    current_price: float = Field(gt=0)
    grams: float | None = Field(default=None, ge=0, description="Defaults to the user's saved holding")
    average_cost: float | None = Field(default=None, ge=0, description="Defaults to the user's saved average cost")
    planned_investment: float | None = Field(default=None, ge=0, description="Defaults to the user's saved plan")
    horizon: str | None = Field(default=None, description="Defaults to the user's saved horizon")
    risk_level: str | None = Field(default=None, description="Defaults to the user's saved risk level")


class BacktestToolQuery(MarketQuery):
    strategy: str = "ma_cross"
    initial_capital: float = Field(default=100000, gt=0)
    transaction_cost_rate: float = Field(default=0.0015, ge=0, le=0.1)
    short_window: int = Field(default=5, ge=2, le=250)
    long_window: int = Field(default=20, ge=3, le=500)


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None
