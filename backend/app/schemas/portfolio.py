"""Portfolio schemas for advisory analysis only."""

from pydantic import BaseModel, Field


class Portfolio(BaseModel):
    grams: float = Field(default=0, ge=0)
    average_cost: float = Field(default=0, ge=0)
    planned_investment: float = Field(default=0, ge=0)
    horizon: str = "medium"
    risk_level: str = "balanced"


class PortfolioAnalysis(BaseModel):
    current_price: float
    market_value: float
    cost_basis: float
    pnl: float
    pnl_pct: float
    break_even_price: float
    risk_level: str
    advisory_only: bool = True

