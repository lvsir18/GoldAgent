"""Market service independent from API and Agent frameworks."""

from __future__ import annotations

from datetime import datetime, time

import pandas as pd

from ..providers.market.base import MarketDataProvider, ProviderFrame, ProviderQuote
from ..schemas.market import MarketHistory, MarketPoint, MarketSummary


class MarketService:
    def __init__(self, provider: MarketDataProvider):
        self.provider = provider

    async def history_frame(self, symbol: str = "AU0", market: str = "CN", period: str = "3y") -> ProviderFrame:
        result = await self.provider.get_history(symbol=symbol, market=market, period=period)
        required = {"open", "high", "low", "close", "volume"}
        missing = required.difference(result.frame.columns)
        if missing:
            raise ValueError(f"Market series is missing columns: {sorted(missing)}")
        clean = result.frame.sort_index().replace([float("inf"), float("-inf")], pd.NA)
        clean = clean.dropna(subset=["open", "high", "low", "close"])
        if clean.empty:
            raise ValueError("Market series has no valid OHLC rows")
        result.frame = clean
        return result

    async def latest_quote(self, symbol: str = "AU0", market: str = "CN") -> ProviderQuote | None:
        get_quote = getattr(self.provider, "get_quote", None)
        if not callable(get_quote):
            return None
        try:
            return await get_quote(symbol, market)
        except (NotImplementedError, ValueError, RuntimeError, OSError):
            return None

    async def history(self, symbol: str = "AU0", market: str = "CN", period: str = "3y", limit: int = 500) -> MarketHistory:
        result = await self.history_frame(symbol, market, period)
        rows = result.frame.tail(max(1, min(limit, 5000)))
        points = [
            MarketPoint(
                timestamp=index.to_pydatetime(),
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row.get("volume", 0)),
            )
            for index, row in rows.iterrows()
        ]
        quote = await self.latest_quote(symbol, market)
        latest_day = rows.index[-1].date()
        if quote and quote.trading_date > latest_day:
            points.append(MarketPoint(
                timestamp=datetime.combine(quote.trading_date, time.min),
                open=quote.open, high=quote.high, low=quote.low, close=quote.price,
                volume=quote.volume, is_provisional=True,
            ))
            result.metadata = quote.metadata.model_copy(update={
                "source": f"{result.metadata.source} + realtime session",
                "data_start": result.metadata.data_start,
            })
        return MarketHistory(points=points, metadata=result.metadata)

    async def summary(self, symbol: str = "AU0", market: str = "CN", period: str = "3y") -> MarketSummary:
        result = await self.history_frame(symbol, market, period)
        close = result.frame["close"].astype(float)

        def change(offset: int) -> float | None:
            if len(close) <= offset or close.iloc[-offset - 1] == 0:
                return None
            return float((close.iloc[-1] / close.iloc[-offset - 1] - 1) * 100)

        quote = await self.latest_quote(symbol, market)
        if not quote:
            return MarketSummary(
                price=float(close.iloc[-1]), previous_close=float(close.iloc[-2]) if len(close) > 1 else None,
                trading_date=close.index[-1].date(),
                change_1d_pct=change(1), change_1w_pct=change(5), change_1m_pct=change(20),
                metadata=result.metadata,
            )

        basis = quote.previous_settlement or quote.previous_close
        daily_change = float((quote.price / basis - 1) * 100) if basis else None

        def quote_change(index: int) -> float | None:
            if len(close) < index or close.iloc[-index] == 0:
                return None
            return float((quote.price / close.iloc[-index] - 1) * 100)

        return MarketSummary(
            price=quote.price,
            previous_close=quote.previous_close,
            previous_settlement=quote.previous_settlement,
            trading_date=quote.trading_date,
            quote_time=quote.quote_time,
            is_realtime=True,
            change_basis="previous_settlement" if quote.previous_settlement else "previous_close",
            change_1d_pct=daily_change,
            change_1w_pct=quote_change(5),
            change_1m_pct=quote_change(20),
            metadata=quote.metadata,
        )
