from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from backend.app.providers.market.base import ProviderFrame
from backend.app.schemas.common import SourceMetadata


@pytest.fixture
def market_frame() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=180, freq="B", tz="UTC")
    trend = np.linspace(450.0, 535.0, len(index))
    wave = np.sin(np.arange(len(index)) / 7) * 5
    close = trend + wave
    return pd.DataFrame(
        {
            "open": close - 1,
            "high": close + 3,
            "low": close - 3,
            "close": close,
            "volume": np.linspace(1000, 2000, len(index)),
        },
        index=index,
    )


@pytest.fixture
def source_metadata() -> SourceMetadata:
    return SourceMetadata(
        source="fixture",
        source_type="simulation",
        currency="CNY",
        market="CN",
        symbol="AU0",
        retrieved_at=datetime.now(timezone.utc),
    )


class FakeMarketProvider:
    def __init__(self, frame: pd.DataFrame, metadata: SourceMetadata):
        self.frame, self.metadata = frame, metadata

    async def get_history(self, symbol: str, market: str, period: str) -> ProviderFrame:
        return ProviderFrame(self.frame.copy(), self.metadata.model_copy(update={"symbol": symbol, "market": market}))

    async def get_exchange_rate(self, pair: str = "USD/CNY"):
        return 7.2, self.metadata
