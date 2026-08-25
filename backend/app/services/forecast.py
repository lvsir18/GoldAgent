"""Forecast model registry and evaluation service."""

from __future__ import annotations

import math
import uuid
from typing import Protocol

import numpy as np
import pandas as pd

from src.indicator_engine import IndicatorEngine

from ..schemas.common import SourceMetadata
from ..schemas.forecast import ForecastMetrics, ForecastRequest, ForecastResult


class ForecastModel(Protocol):
    name: str

    def predict(self, values: np.ndarray, horizon: int) -> np.ndarray: ...


class BaselineForecastModel:
    def __init__(self, name: str, config: dict | None = None):
        self.name = name
        self.engine = IndicatorEngine(config=config or {})

    def predict(self, values: np.ndarray, horizon: int) -> np.ndarray:
        frame = pd.DataFrame({"close": values})
        result = self.engine.forecast_trend(frame, periods=horizon, column="close", method=self.name)
        if not result:
            raise ValueError("Forecast model failed")
        return np.asarray(result["forecast_prices"], dtype=float)


class ForecastService:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.models = {name: BaselineForecastModel(name, self.config) for name in ("linear", "ma", "exponential")}

    def forecast(self, frame: pd.DataFrame, metadata: SourceMetadata, request: ForecastRequest) -> ForecastResult:
        values = frame["close"].dropna().astype(float).to_numpy()
        if request.lookback:
            values = values[-request.lookback :]
        if len(values) < 20:
            raise ValueError("At least 20 observations are required")
        predicted = self.models[request.model].predict(values, request.horizon)
        current = float(values[-1])
        changes = ((predicted / current) - 1) * 100
        return ForecastResult(
            id=str(uuid.uuid4()), request=request, current_price=current,
            predicted_prices=predicted.tolist(), predicted_change_pct=changes.tolist(), metadata=metadata,
        )

    def evaluate(self, values: np.ndarray, model: str, horizon: int = 1, min_train: int = 30) -> ForecastMetrics:
        actual, predicted = [], []
        for endpoint in range(min_train, len(values) - horizon + 1):
            train = values[:endpoint]
            pred = self.models[model].predict(train, horizon)[-1]
            predicted.append(float(pred))
            actual.append(float(values[endpoint + horizon - 1]))
        if not actual:
            return ForecastMetrics()
        a, p = np.asarray(actual), np.asarray(predicted)
        errors = p - a
        mae = float(np.mean(np.abs(errors)))
        rmse = float(math.sqrt(np.mean(errors**2)))
        nonzero = a != 0
        mape = float(np.mean(np.abs(errors[nonzero] / a[nonzero])) * 100) if nonzero.any() else None
        previous = values[min_train - 1 : len(values) - horizon]
        direction_accuracy = float(np.mean(np.sign(p - previous) == np.sign(a - previous)))
        return ForecastMetrics(mae=mae, rmse=rmse, mape=mape, direction_accuracy=direction_accuracy)

