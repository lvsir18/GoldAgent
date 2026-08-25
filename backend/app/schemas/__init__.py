"""Public Pydantic schemas."""

from .backtest import BacktestRequest, BacktestResult
from .common import ApiError, ApiResponse, SourceMetadata
from .forecast import ForecastRequest, ForecastResult
from .market import MarketHistory, MarketPoint, MarketSummary, TechnicalSnapshot
from .news import NewsArticle, NewsSearchResult
from .portfolio import Portfolio, PortfolioAnalysis

__all__ = [
    "ApiError", "ApiResponse", "SourceMetadata", "MarketHistory", "MarketPoint",
    "MarketSummary", "TechnicalSnapshot", "NewsArticle", "NewsSearchResult",
    "ForecastRequest", "ForecastResult", "BacktestRequest", "BacktestResult",
    "Portfolio", "PortfolioAnalysis",
]
