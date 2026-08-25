"""Explicit dependency container; no framework-specific globals."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from src.settings import AppSettings

from ..providers.market.legacy_akshare import LegacyAkShareProvider
from ..providers.news.tavily import TavilyNewsProvider
from ..services.forecast import ForecastService
from ..services.market import MarketService
from ..services.news import NewsService
from ..services.portfolio import PortfolioService
from ..services.technical import TechnicalAnalysisService
from ..services.backtest import BacktestService
from ..services.reports import ReportService


@dataclass(slots=True)
class ServiceContainer:
    settings: AppSettings
    market: MarketService
    technical: TechnicalAnalysisService
    forecast: ForecastService
    news: NewsService
    portfolio: PortfolioService
    backtest: BacktestService
    reports: ReportService


@lru_cache(maxsize=1)
def _build_default_container() -> ServiceContainer:
    root = Path(__file__).resolve().parents[3]
    settings = AppSettings.load(root / "config.yaml")
    return build_container(settings)


def build_container(settings: AppSettings | None = None) -> ServiceContainer:
    if settings is None:
        return _build_default_container()
    market_provider = LegacyAkShareProvider()
    news_provider = TavilyNewsProvider(timeout_seconds=settings.tavily.timeout)
    return ServiceContainer(
        settings=settings,
        market=MarketService(market_provider),
        technical=TechnicalAnalysisService(settings.indicators),
        forecast=ForecastService(settings.forecast.model_dump()),
        news=NewsService(news_provider),
        portfolio=PortfolioService(),
        backtest=BacktestService(),
        reports=ReportService(),
    )
