"""Regression tests for the product audit's reproducible correctness defects."""
import numpy as np
import pandas as pd
import pytest
from langchain_core.messages import SystemMessage

from backend.app.agent.graph import GoldAgentRuntime
from backend.app.llm.base import ChatResponse
from backend.app.tools.registry import ToolRegistry
from backend.app.schemas.backtest import BacktestRequest
from backend.app.schemas.forecast import ForecastRequest
from backend.app.services.backtest import BacktestService
from backend.app.services.forecast import ForecastService
from src.settings import AppSettings


def test_backtest_reconciles_cash_positions_fees_and_pnl():
    prices = 500 + np.sin(np.arange(160) / 6) * 35
    data = pd.DataFrame({"close": prices, "open": prices + 2}, index=pd.date_range("2025-01-01", periods=160))
    request = BacktestRequest(parameters={"short_window": 3, "long_window": 10})
    result = BacktestService().run(data, request)
    cash, quantity = request.initial_capital, 0
    assert len(result.trades) > 4
    for trade in result.trades:
        assert trade.price == data.loc[trade.timestamp, "open"]
        if trade.action == "buy":
            cash -= trade.quantity * trade.price + trade.cost
            quantity += trade.quantity
        else:
            assert trade.quantity == pytest.approx(quantity)
            cash += trade.quantity * trade.price - trade.cost
            quantity -= trade.quantity
        assert cash == pytest.approx(trade.cash_after, abs=1e-7)
        assert quantity == pytest.approx(trade.position_after)
    final = cash + quantity * prices[-1]
    assert final == pytest.approx(result.equity_curve[-1]["value"])
    assert sum(t.cost for t in result.trades) == pytest.approx(result.metrics.transaction_cost)
    assert final - request.initial_capital == pytest.approx(result.ledger["realized_pnl"] + result.ledger["unrealized_pnl"])


def test_forecast_evaluates_selected_horizon_and_lookback(market_frame, source_metadata):
    result = ForecastService().evaluated_forecast(market_frame, source_metadata, ForecastRequest(model="linear", horizon=5, lookback=45))
    assert result.metrics.horizon == 5
    assert result.metrics.sample_count == 11
    assert result.metrics.baseline_mae is not None
    assert result.metrics.evaluation_end == str(market_frame.index[-1])


async def test_updated_context_replaces_previous_system_message():
    class CaptureGateway:
        calls = []
        async def chat(self, messages, tools=None):
            self.calls.append(list(messages))
            return ChatResponse(content="收到")
    gateway = CaptureGateway()
    runtime = GoldAgentRuntime(AppSettings(), gateway, ToolRegistry([]))
    await runtime.invoke(user_message="first", user_id="u", session_id="s", user_preferences={"custom_instructions": "OLD_PREFERENCE"})
    await runtime.invoke(user_message="second", user_id="u", session_id="s", user_preferences={"custom_instructions": "NEW_PREFERENCE"})
    systems = [m for m in gateway.calls[-1] if isinstance(m, SystemMessage)]
    assert len(systems) == 1
    assert "NEW_PREFERENCE" in systems[0].content
    assert "OLD_PREFERENCE" not in systems[0].content
    assert any(m.content == "first" for m in gateway.calls[-1])
