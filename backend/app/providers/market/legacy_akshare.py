"""Compatibility adapter around the existing AkShare data fetcher."""

from __future__ import annotations

import asyncio
import re
import time as monotonic_time
from datetime import datetime, time, timezone

import akshare as ak

from src.data_fetcher import DataFetcher

from ...schemas.common import SourceMetadata
from .base import ProviderFrame, ProviderQuote


class LegacyAkShareProvider:
    """Expose legacy AkShare fetching without misrepresenting derived data."""

    def __init__(self, fetcher: DataFetcher | None = None):
        self.fetcher = fetcher or DataFetcher()
        self._quote_cache: dict[tuple[str, str], tuple[float, ProviderQuote]] = {}
        self._quote_lock = asyncio.Lock()

    async def get_history(self, symbol: str, market: str, period: str) -> ProviderFrame:
        normalized_market = market.upper()
        if normalized_market == "CN":
            frame = await asyncio.to_thread(self.fetcher.fetch_domestic_gold, symbol, period)
            source_type = "direct"
            currency = "CNY/g"
            source = "AkShare/Sina Futures"
            is_derived = False
        else:
            frame = await asyncio.to_thread(self.fetcher.fetch_international_gold, symbol, period)
            source_type = "derived"
            currency = "USD/oz"
            source = "Derived from AkShare AU0 and USD/CNY"
            is_derived = True
        if frame.empty:
            raise ValueError("Provider returned an empty market series")
        metadata = SourceMetadata(
            source=source,
            source_type=source_type,
            is_derived=is_derived,
            data_start=frame.index.min().to_pydatetime().replace(tzinfo=timezone.utc),
            data_end=frame.index.max().to_pydatetime().replace(tzinfo=timezone.utc),
            currency=currency,
            market=normalized_market,
            symbol=symbol,
            reference="akshare",
        )
        return ProviderFrame(frame=frame, metadata=metadata)

    async def get_exchange_rate(self, pair: str = "USD/CNY"):
        raise NotImplementedError("FX extraction will be moved out of the legacy combined fetcher")

    async def get_quote(self, symbol: str, market: str) -> ProviderQuote:
        normalized_market = market.upper()
        if normalized_market != "CN":
            raise NotImplementedError("Realtime quotes are currently available only for the CN market")
        key = (symbol.upper(), normalized_market)
        now = monotonic_time.monotonic()
        cached = self._quote_cache.get(key)
        if cached and now - cached[0] < 5:
            return cached[1]
        async with self._quote_lock:
            now = monotonic_time.monotonic()
            cached = self._quote_cache.get(key)
            if cached and now - cached[0] < 5:
                return cached[1]
            quote = await asyncio.to_thread(self._fetch_realtime_quote, symbol, normalized_market)
            self._quote_cache[key] = (monotonic_time.monotonic(), quote)
            return quote

    @staticmethod
    def _fetch_realtime_quote(symbol: str, market: str) -> ProviderQuote:
        product_code = re.match(r"[A-Za-z]+", symbol)
        product_name = {"AU": "黄金"}.get(product_code.group(0).upper() if product_code else "")
        if not product_name:
            raise ValueError(f"Realtime quote mapping is unavailable for {symbol}")
        frame = ak.futures_zh_realtime(symbol=product_name)
        matches = frame[frame["symbol"].astype(str).str.upper() == symbol.upper()]
        if matches.empty:
            raise ValueError(f"Realtime provider did not return {symbol}")
        row = matches.iloc[0]

        def number(name: str) -> float | None:
            value = row.get(name)
            if value is None:
                return None
            try:
                parsed = float(value)
                return parsed if parsed == parsed else None
            except (TypeError, ValueError):
                return None

        price = number("trade")
        if price is None or price <= 0:
            raise ValueError(f"Realtime provider returned an invalid trade price for {symbol}")
        trading_date = datetime.strptime(str(row["tradedate"]), "%Y-%m-%d").date()
        raw_time = str(row.get("ticktime") or "").strip()
        quote_time = time.fromisoformat(raw_time) if raw_time else None
        metadata = SourceMetadata(
            source="AkShare/Sina Futures Realtime",
            source_type="direct",
            currency="CNY/g",
            market=market,
            symbol=symbol,
            data_end=datetime.combine(trading_date, time.min, tzinfo=timezone.utc),
            reference="akshare:futures_zh_realtime",
        )
        return ProviderQuote(
            price=price,
            open=number("open") or price,
            high=number("high") or price,
            low=number("low") or price,
            volume=number("volume") or 0,
            previous_close=number("preclose"),
            previous_settlement=number("prevsettlement") or number("presettlement"),
            trading_date=trading_date,
            quote_time=quote_time,
            metadata=metadata,
        )
