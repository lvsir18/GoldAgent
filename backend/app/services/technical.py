"""Technical analysis service around tested numerical code."""

from __future__ import annotations

import math

import pandas as pd

from src.indicator_engine import IndicatorEngine

from ..schemas.common import SourceMetadata
from ..schemas.market import TechnicalSnapshot


def _finite(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


class TechnicalAnalysisService:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.engine = IndicatorEngine(config=self.config)

    def calculate(self, frame: pd.DataFrame, metadata: SourceMetadata) -> tuple[pd.DataFrame, TechnicalSnapshot]:
        calculated = self.engine.calculate_all_indicators(frame.copy(), self.config)
        latest = calculated.iloc[-1]
        ma = {key: _finite(latest.get(key)) for key in calculated.columns if key.startswith("ma")}
        close = float(latest["close"])
        ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
        if pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60) and ma5 > ma20 > ma60:
            trend = "uptrend"
        elif pd.notna(ma5) and pd.notna(ma20) and pd.notna(ma60) and ma5 < ma20 < ma60:
            trend = "downtrend"
        else:
            trend = "consolidation"
        returns = calculated["close"].pct_change().tail(20)
        snapshot = TechnicalSnapshot(
            timestamp=calculated.index[-1].to_pydatetime(), close=close, ma=ma,
            rsi=_finite(latest.get("rsi")),
            macd=_finite(next((latest[c] for c in calculated.columns if c.startswith("MACD_") and not c.startswith("MACDh") and not c.startswith("MACDs")), None)),
            macd_signal=_finite(next((latest[c] for c in calculated.columns if c.startswith("MACDs")), None)),
            atr=_finite(next((latest[c] for c in calculated.columns if c.startswith("ATR")), None)),
            volatility=_finite(returns.std()), trend=trend,
            support=float(calculated["low"].tail(20).min()),
            resistance=float(calculated["high"].tail(20).max()), metadata=metadata,
        )
        return calculated, snapshot

