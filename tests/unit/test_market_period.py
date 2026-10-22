import pandas as pd
import pytest
from pydantic import ValidationError
from backend.app.core.market_period import normalize_period
from backend.app.tools.schemas import MarketHistoryQuery
from backend.app.services.market import MarketService
from tests.conftest import FakeMarketProvider


@pytest.mark.parametrize("value,expected", [("1mo","1mo"),("1m","1mo"),(" 2MO ","2mo"),("2w","2w"),("30d","30d"),("3y","3y"),("max","all")])
def test_tool_period_accepts_common_calendar_aliases(value, expected):
    assert MarketHistoryQuery(period=value).period == expected


@pytest.mark.parametrize("value", ["0mo", "1minute", "-1y", "forever", "999999y"])
def test_invalid_periods_are_still_rejected(value):
    with pytest.raises((ValueError, ValidationError)):
        normalize_period(value)


@pytest.mark.parametrize("period,offset", [("1mo",pd.DateOffset(months=1)),("1m",pd.DateOffset(months=1)),("2w",pd.DateOffset(weeks=2)),("10d",pd.DateOffset(days=10))])
async def test_history_window_is_actually_applied(period, offset, market_frame, source_metadata):
    service = MarketService(FakeMarketProvider(market_frame,source_metadata))
    result = await service.history_frame(period=period)
    expected = market_frame.loc[market_frame.index >= market_frame.index[-1] - offset]
    assert list(result.frame.index) == list(expected.index)
    assert result.metadata.data_start == expected.index[0].to_pydatetime()
    assert result.metadata.data_end == expected.index[-1].to_pydatetime()
