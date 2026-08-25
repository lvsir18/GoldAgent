from __future__ import annotations

from datetime import date, time

import numpy as np
import pandas as pd

from backend.app.providers.market.base import ProviderQuote
from backend.app.providers.market.legacy_akshare import LegacyAkShareProvider
from backend.app.schemas.backtest import BacktestRequest
from backend.app.schemas.forecast import ForecastRequest
from backend.app.schemas.portfolio import Portfolio
from backend.app.services.backtest import BacktestService
from backend.app.services.forecast import ForecastService
from backend.app.services.market import MarketService
from backend.app.services.portfolio import PortfolioService
from backend.app.services.technical import TechnicalAnalysisService
from tests.conftest import FakeMarketProvider


async def test_market_and_technical_services(market_frame, source_metadata):
    service = MarketService(FakeMarketProvider(market_frame, source_metadata))
    summary = await service.summary()
    history = await service.history(limit=25)
    _, snapshot = TechnicalAnalysisService().calculate(market_frame, source_metadata)
    assert summary.price == market_frame.close.iloc[-1]
    assert len(history.points) == 25
    assert snapshot.support < snapshot.resistance
    assert snapshot.trend in {"uptrend", "downtrend", "consolidation"}


async def test_realtime_quote_drives_summary_and_appends_provisional_candle(market_frame, source_metadata):
    class RealtimeProvider(FakeMarketProvider):
        async def get_quote(self, symbol: str, market: str) -> ProviderQuote:
            return ProviderQuote(
                price=1001.88,
                open=990.52,
                high=1002.96,
                low=990.16,
                volume=207842,
                previous_close=987.44,
                previous_settlement=978.80,
                trading_date=date(2026, 8, 24),
                quote_time=time(2, 30),
                metadata=source_metadata.model_copy(update={"source": "realtime"}),
            )

    service = MarketService(RealtimeProvider(market_frame, source_metadata))
    summary = await service.summary()
    history = await service.history(limit=25)
    assert summary.price == 1001.88
    assert summary.previous_close == 987.44
    assert summary.previous_settlement == 978.80
    assert summary.trading_date == date(2026, 8, 24)
    assert summary.is_realtime is True
    assert summary.change_basis == "previous_settlement"
    assert history.points[-1].close == 1001.88
    assert history.points[-1].is_provisional is True
    assert len(history.points) == 26


def test_legacy_akshare_realtime_quote_mapping(monkeypatch):
    raw = pd.DataFrame([{
        "symbol": "AU0", "trade": 1001.88, "open": 990.52, "high": 1002.96,
        "low": 990.16, "volume": 207842, "preclose": 987.44,
        "prevsettlement": 978.80, "tradedate": "2026-08-24", "ticktime": "02:30:00",
    }])
    monkeypatch.setattr(
        "backend.app.providers.market.legacy_akshare.ak.futures_zh_realtime",
        lambda symbol: raw,
    )
    quote = LegacyAkShareProvider._fetch_realtime_quote("AU0", "CN")
    assert quote.price == 1001.88
    assert quote.previous_close == 987.44
    assert quote.previous_settlement == 978.80
    assert quote.trading_date == date(2026, 8, 24)
    assert quote.quote_time == time(2, 30)


def test_forecast_and_walk_forward_metrics(market_frame, source_metadata):
    service = ForecastService()
    result = service.forecast(market_frame, source_metadata, ForecastRequest(horizon=5, model="linear"))
    metrics = service.evaluate(market_frame.close.to_numpy(), "linear", horizon=1)
    assert len(result.predicted_prices) == 5
    assert result.metadata.source == "fixture"
    assert metrics.mae is not None and metrics.mae >= 0


def test_backtest_has_costs_benchmark_and_bounded_drawdown(market_frame):
    request = BacktestRequest(parameters={"short_window": 5, "long_window": 20}, transaction_cost_rate=0.002)
    result = BacktestService().run(market_frame, request)
    assert result.metrics.transaction_cost >= 0
    assert result.metrics.maximum_drawdown <= 0
    assert np.isfinite(result.metrics.benchmark_return)
    assert len(result.equity_curve) == len(market_frame)


def test_portfolio_math():
    result = PortfolioService().analyze(Portfolio(grams=20, average_cost=500), current_price=525)
    assert result.market_value == 10500
    assert result.pnl == 500
    assert result.pnl_pct == 5
