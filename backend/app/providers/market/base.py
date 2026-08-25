"""Market provider contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from typing import Protocol

import pandas as pd

from ...schemas.common import SourceMetadata


@dataclass(slots=True)
class ProviderFrame:
    frame: pd.DataFrame
    metadata: SourceMetadata


@dataclass(slots=True)
class ProviderQuote:
    price: float
    open: float
    high: float
    low: float
    volume: float
    previous_close: float | None
    previous_settlement: float | None
    trading_date: date
    quote_time: time | None
    metadata: SourceMetadata


class MarketDataProvider(Protocol):
    async def get_history(self, symbol: str, market: str, period: str) -> ProviderFrame:
        """Return normalized OHLCV history and truthful provenance metadata."""

    async def get_exchange_rate(self, pair: str = "USD/CNY") -> tuple[float, SourceMetadata]:
        """Return the latest exchange rate."""

    async def get_quote(self, symbol: str, market: str) -> ProviderQuote:
        """Return the latest available quote, including an in-progress session."""
