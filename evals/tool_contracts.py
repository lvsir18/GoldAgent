"""Use the production input schemas instead of accepting any argument dict."""
from backend.app.tools.schemas import (
    MarketQuery, MarketHistoryQuery, TechnicalQuery, NewsQuery,
    ForecastToolQuery, PortfolioToolQuery, BacktestToolQuery, KnowledgeQuery,
)

SCHEMAS = dict(zip([
    "get_gold_spot_price", "get_market_history", "calculate_technical_indicators",
    "search_financial_news", "forecast_gold_price", "analyze_portfolio",
    "run_backtest", "retrieve_financial_knowledge",
], [MarketQuery, MarketHistoryQuery, TechnicalQuery, NewsQuery,
    ForecastToolQuery, PortfolioToolQuery, BacktestToolQuery, KnowledgeQuery], strict=True))
