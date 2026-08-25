from backend.app.core.container import ServiceContainer
from backend.app.services.backtest import BacktestService
from backend.app.services.forecast import ForecastService
from backend.app.services.market import MarketService
from backend.app.services.portfolio import PortfolioService
from backend.app.services.reports import ReportService
from backend.app.services.technical import TechnicalAnalysisService
from backend.app.services.news import NewsService
from backend.app.tools.registry import build_tool_registry
from src.settings import AppSettings
from tests.conftest import FakeMarketProvider


class NoNews:
    async def search(self, query: str, max_results: int):
        raise RuntimeError("offline")


def test_registry_exposes_bounded_typed_tools(market_frame, source_metadata):
    container = ServiceContainer(
        settings=AppSettings(), market=MarketService(FakeMarketProvider(market_frame, source_metadata)),
        technical=TechnicalAnalysisService(), forecast=ForecastService(), news=NewsService(NoNews()),
        portfolio=PortfolioService(), backtest=BacktestService(), reports=ReportService(),
    )
    registry = build_tool_registry(container)
    assert set(registry.names()) == {
        "analyze_portfolio", "calculate_technical_indicators", "forecast_gold_price",
        "get_gold_spot_price", "get_market_history", "run_backtest", "search_financial_news",
    }
    assert registry.get("get_market_history").args_schema.model_json_schema()["properties"]["limit"]["maximum"] == 500
