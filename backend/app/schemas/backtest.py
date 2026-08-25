"""Backtest boundary schemas."""

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    strategy: str = "ma_cross"
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float = Field(default=100000, gt=0)
    transaction_cost_rate: float = Field(default=0.0015, ge=0, le=0.1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class BacktestTrade(BaseModel):
    timestamp: datetime
    action: str
    price: float
    quantity: float
    cost: float
    pnl: float | None = None


class BacktestMetrics(BaseModel):
    cumulative_return: float
    annualized_return: float
    maximum_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    turnover: float
    transaction_cost: float
    benchmark_return: float


class BacktestResult(BaseModel):
    id: str
    status: str = "completed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    request: BacktestRequest
    metrics: BacktestMetrics
    equity_curve: list[dict[str, float | str]]
    drawdown_curve: list[dict[str, float | str]]
    trades: list[BacktestTrade]

