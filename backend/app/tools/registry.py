"""Structured Tool registry backed by domain services."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from langchain_core.tools import BaseTool, StructuredTool

from ..core.container import ServiceContainer, build_container
from ..schemas.forecast import ForecastRequest
from ..schemas.portfolio import Portfolio
from .schemas import (
    ForecastToolQuery,
    MarketHistoryQuery,
    MarketQuery,
    NewsQuery,
    PortfolioToolQuery,
    TechnicalQuery,
    BacktestToolQuery,
    KnowledgeQuery,
)
from ..rag.service import KnowledgeService
from ..schemas.backtest import BacktestRequest


class ToolRegistry:
    def __init__(self, tools: list[BaseTool]):
        self._tools = {tool.name: tool for tool in tools}

    @property
    def tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)


def _bounded(fn: Callable[..., Awaitable[Any]], timeout_seconds: int):
    async def invoke(**kwargs):
        return await asyncio.wait_for(fn(**kwargs), timeout=timeout_seconds)

    return invoke


def build_tool_registry(
    container: ServiceContainer | None = None,
    knowledge: KnowledgeService | None = None,
    user_id: str | None = None,
    portfolio_context: dict[str, Any] | None = None,
    risk_profile: dict[str, Any] | None = None,
) -> ToolRegistry:
    services = container or build_container()
    timeout = services.settings.agent.tool_timeout_seconds

    async def get_gold_spot_price(symbol: str = "AU0", market: str = "CN", period: str = "3y") -> dict:
        """Get the latest gold price and truthful source/freshness metadata."""
        result = await services.market.summary(symbol, market, period)
        return result.model_dump(mode="json")

    async def get_market_history(symbol: str = "AU0", market: str = "CN", period: str = "3y", limit: int = 120) -> dict:
        """Get bounded OHLCV gold history for charts or calculations."""
        result = await services.market.history(symbol, market, period, limit)
        return result.model_dump(mode="json")

    async def calculate_technical_indicators(symbol: str = "AU0", market: str = "CN", period: str = "3y") -> dict:
        """Calculate MA, RSI, MACD, ATR, volatility, trend, support and resistance."""
        provider_frame = await services.market.history_frame(symbol, market, period)
        _, snapshot = services.technical.calculate(provider_frame.frame, provider_frame.metadata)
        return snapshot.model_dump(mode="json")

    async def search_financial_news(query: str, max_results: int = 10) -> dict:
        """Search current financial news. Failure is explicit; no synthetic articles are returned."""
        result = await services.news.search(query, max_results)
        return result.model_dump(mode="json")

    async def forecast_gold_price(
        symbol: str = "AU0", market: str = "CN", period: str = "3y",
        horizon: int = 5, model: str = "exponential", lookback: int | None = None,
    ) -> dict:
        """Run a baseline gold forecast clearly labelled as a model estimate."""
        provider_frame = await services.market.history_frame(symbol, market, period)
        request = ForecastRequest(symbol=symbol, horizon=horizon, model=model, lookback=lookback)
        result = services.forecast.forecast(provider_frame.frame, provider_frame.metadata, request)
        return result.model_dump(mode="json")

    async def analyze_portfolio(
        current_price: float, grams: float | None = None, average_cost: float | None = None,
        planned_investment: float | None = None, horizon: str | None = None,
        risk_level: str | None = None,
    ) -> dict:
        """Analyze PnL using the user's saved portfolio by default; never place trades."""
        saved = portfolio_context or {}
        resolved_grams = saved.get("grams") if grams is None else grams
        resolved_cost = saved.get("average_cost") if average_cost is None else average_cost
        if resolved_grams is None or resolved_cost is None or (grams is None and float(resolved_grams) <= 0):
            raise ValueError("No saved portfolio is available; grams and average_cost are required")
        portfolio = Portfolio(
            grams=resolved_grams,
            average_cost=resolved_cost,
            planned_investment=saved.get("planned_investment", 0) if planned_investment is None else planned_investment,
            horizon=horizon or (risk_profile or {}).get("horizon", "medium"),
            risk_level=risk_level or (risk_profile or {}).get("risk_level", "balanced"),
        )
        return services.portfolio.analyze(portfolio, current_price).model_dump(mode="json")

    async def run_backtest(
        symbol: str = "AU0", market: str = "CN", period: str = "3y", strategy: str = "ma_cross",
        initial_capital: float = 100000, transaction_cost_rate: float = 0.0015,
        short_window: int = 5, long_window: int = 20,
    ) -> dict:
        """Run a no-look-ahead MA backtest with transaction costs and benchmark metrics."""
        source = await services.market.history_frame(symbol, market, period)
        request = BacktestRequest(
            strategy=strategy, initial_capital=initial_capital,
            transaction_cost_rate=transaction_cost_rate,
            parameters={"short_window": short_window, "long_window": long_window},
        )
        return services.backtest.run(source.frame, request).model_dump(mode="json")

    specs = [
        ("get_gold_spot_price", get_gold_spot_price, MarketQuery),
        ("get_market_history", get_market_history, MarketHistoryQuery),
        ("calculate_technical_indicators", calculate_technical_indicators, TechnicalQuery),
        ("search_financial_news", search_financial_news, NewsQuery),
        ("forecast_gold_price", forecast_gold_price, ForecastToolQuery),
        ("analyze_portfolio", analyze_portfolio, PortfolioToolQuery),
        ("run_backtest", run_backtest, BacktestToolQuery),
    ]
    if knowledge is not None and user_id is not None:
        async def retrieve_financial_knowledge(query: str, top_k: int = 5, document_id: str | None = None) -> dict:
            """Retrieve tenant-scoped long-term knowledge with chunk-level sources."""
            items = await knowledge.search(user_id, query, top_k, document_id)
            return {"query": query, "results": items, "source": "Knowledge Base"}
        specs.append(("retrieve_financial_knowledge", retrieve_financial_knowledge, KnowledgeQuery))
    tools = [
        StructuredTool.from_function(
            coroutine=_bounded(function, timeout),
            name=name,
            description=(function.__doc__ or name).strip(),
            args_schema=schema,
        )
        for name, function, schema in specs
    ]
    return ToolRegistry(tools)
