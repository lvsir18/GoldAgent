"""Deterministic portfolio calculations, separate from prompts."""

from ..schemas.portfolio import Portfolio, PortfolioAnalysis


class PortfolioService:
    def analyze(self, portfolio: Portfolio, current_price: float) -> PortfolioAnalysis:
        market_value = portfolio.grams * current_price
        cost_basis = portfolio.grams * portfolio.average_cost
        pnl = market_value - cost_basis
        pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
        return PortfolioAnalysis(
            current_price=current_price, market_value=market_value, cost_basis=cost_basis,
            pnl=pnl, pnl_pct=pnl_pct, break_even_price=portfolio.average_cost,
            risk_level=portfolio.risk_level,
        )

