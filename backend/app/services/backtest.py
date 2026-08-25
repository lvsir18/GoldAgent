"""Vectorized, long-only backtesting with explicit signal lag."""

from __future__ import annotations

import math
import uuid

import numpy as np
import pandas as pd

from ..schemas.backtest import BacktestMetrics, BacktestRequest, BacktestResult, BacktestTrade


class BacktestService:
    def run(self, frame: pd.DataFrame, request: BacktestRequest) -> BacktestResult:
        data = frame.sort_index().copy()
        if request.start_date:
            data = data[data.index.date >= request.start_date]
        if request.end_date:
            data = data[data.index.date <= request.end_date]
        if len(data) < 30:
            raise ValueError("Backtest requires at least 30 observations")

        short = int(request.parameters.get("short_window", 5))
        long = int(request.parameters.get("long_window", 20))
        if short < 2 or long <= short:
            raise ValueError("Require 2 <= short_window < long_window")

        close = data["close"].astype(float)
        fast = close.rolling(short).mean()
        slow = close.rolling(long).mean()
        signal = (fast > slow).astype(float)
        # A signal observed at t can only be executed for the t+1 return.
        position = signal.shift(1).fillna(0)
        returns = close.pct_change().fillna(0)
        trades_delta = position.diff().fillna(position).abs()
        costs = trades_delta * request.transaction_cost_rate
        strategy_returns = position * returns - costs
        equity = request.initial_capital * (1 + strategy_returns).cumprod()
        benchmark = request.initial_capital * (1 + returns).cumprod()
        running_max = equity.cummax()
        drawdown = equity / running_max - 1

        elapsed_days = max((data.index[-1] - data.index[0]).days, 1)
        years = elapsed_days / 365.25
        cumulative = float(equity.iloc[-1] / request.initial_capital - 1)
        annualized = float((1 + cumulative) ** (1 / years) - 1) if cumulative > -1 else -1.0
        periods_per_year = 252 if elapsed_days / len(data) < 3 else 52
        std = float(strategy_returns.std())
        sharpe = float(strategy_returns.mean() / std * math.sqrt(periods_per_year)) if std > 0 else 0.0
        benchmark_return = float(benchmark.iloc[-1] / request.initial_capital - 1)

        trade_list: list[BacktestTrade] = []
        entry_price: float | None = None
        closed_returns: list[float] = []
        capital = request.initial_capital
        for index, delta in position.diff().fillna(position).items():
            if delta == 0:
                continue
            price = float(close.loc[index])
            action = "buy" if delta > 0 else "sell"
            quantity = capital / price if price else 0
            cost = capital * request.transaction_cost_rate
            pnl = None
            if action == "buy":
                entry_price = price
            elif entry_price:
                trade_return = (price / entry_price - 1) - 2 * request.transaction_cost_rate
                closed_returns.append(trade_return)
                pnl = capital * trade_return
                entry_price = None
            trade_list.append(BacktestTrade(timestamp=index.to_pydatetime(), action=action, price=price, quantity=quantity, cost=cost, pnl=pnl))

        metrics = BacktestMetrics(
            cumulative_return=cumulative,
            annualized_return=annualized,
            maximum_drawdown=float(drawdown.min()),
            sharpe_ratio=sharpe,
            win_rate=float(np.mean(np.asarray(closed_returns) > 0)) if closed_returns else 0.0,
            trade_count=len(trade_list),
            turnover=float(trades_delta.sum()),
            transaction_cost=float((costs * equity.shift(1).fillna(request.initial_capital)).sum()),
            benchmark_return=benchmark_return,
        )
        equity_curve = [{"timestamp": index.isoformat(), "value": float(value)} for index, value in equity.items()]
        drawdown_curve = [{"timestamp": index.isoformat(), "value": float(value)} for index, value in drawdown.items()]
        return BacktestResult(
            id=str(uuid.uuid4()), request=request, metrics=metrics,
            equity_curve=equity_curve, drawdown_curve=drawdown_curve, trades=trade_list,
        )

