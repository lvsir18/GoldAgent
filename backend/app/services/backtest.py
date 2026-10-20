"""Cash/position ledger. Observe yesterday's close, execute at today's open."""

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
        short = int(request.parameters.get("short_window", 5))
        long = int(request.parameters.get("long_window", 20))
        if short < 2 or long <= short:
            raise ValueError("Require 2 <= short_window < long_window")
        if len(data) < max(30, long + 2):
            raise ValueError("Not enough observations for the selected windows")
        if request.strategy != "ma_cross":
            raise ValueError("Unsupported strategy")

        close = data["close"].astype(float)
        opening = data["open"].astype(float) if "open" in data else close.shift(1).fillna(close.iloc[0])
        if not np.isfinite(close).all() or not np.isfinite(opening).all() or (close <= 0).any() or (opening <= 0).any():
            raise ValueError("Prices must be finite and positive")
        fast = close.rolling(short).mean()
        slow = close.rolling(long).mean()
        signal = (fast > slow).shift(1, fill_value=False)
        cash, quantity, entry_total = request.initial_capital, 0.0, 0.0
        rate = request.transaction_cost_rate
        trade_list: list[BacktestTrade] = []
        closed_returns: list[float] = []
        values: list[float] = []
        for index, holding in signal.items():
            price = float(opening.loc[index])
            pnl = None
            if holding and quantity == 0:
                quantity = cash / (price * (1 + rate))
                gross = quantity * price
                cost = gross * rate
                entry_total = gross + cost
                cash = max(0.0, cash - entry_total)
                traded_quantity, action = quantity, "buy"
            elif not holding and quantity > 0:
                traded_quantity, action = quantity, "sell"
                gross = quantity * price
                cost = gross * rate
                proceeds = gross - cost
                pnl = proceeds - entry_total
                closed_returns.append(pnl / entry_total)
                cash += proceeds
                quantity, entry_total = 0.0, 0.0
            else:
                values.append(cash + quantity * float(close.loc[index]))
                continue
            trade_list.append(BacktestTrade(timestamp=index.to_pydatetime(), action=action, price=price,
                quantity=traded_quantity, cost=cost, pnl=pnl, cash_after=cash, position_after=quantity))
            values.append(cash + quantity * float(close.loc[index]))
        equity = pd.Series(values, index=data.index)
        strategy_returns = equity.pct_change().fillna(equity.iloc[0] / request.initial_capital - 1)
        # The benchmark pays the same entry fee and also carries its final position.
        benchmark = request.initial_capital / (float(opening.iloc[0]) * (1 + rate)) * close
        running_max = equity.cummax().clip(lower=request.initial_capital)
        drawdown = equity / running_max - 1

        elapsed_days = max((data.index[-1] - data.index[0]).days, 1)
        years = elapsed_days / 365.25
        cumulative = float(equity.iloc[-1] / request.initial_capital - 1)
        annualized = float((1 + cumulative) ** (1 / years) - 1) if cumulative > -1 else -1.0
        periods_per_year = 252 if elapsed_days / len(data) < 3 else 52
        std = float(strategy_returns.std())
        sharpe = float(strategy_returns.mean() / std * math.sqrt(periods_per_year)) if std > 0 else 0.0
        benchmark_return = float(benchmark.iloc[-1] / request.initial_capital - 1)

        metrics = BacktestMetrics(
            cumulative_return=cumulative,
            annualized_return=annualized,
            maximum_drawdown=float(drawdown.min()),
            sharpe_ratio=sharpe,
            win_rate=float(np.mean(np.asarray(closed_returns) > 0)) if closed_returns else 0.0,
            trade_count=len(trade_list),
            turnover=sum(t.price * t.quantity for t in trade_list) / request.initial_capital,
            transaction_cost=sum(t.cost for t in trade_list),
            benchmark_return=benchmark_return,
        )
        equity_curve = [{"timestamp": index.isoformat(), "value": float(value)} for index, value in equity.items()]
        drawdown_curve = [{"timestamp": index.isoformat(), "value": float(value)} for index, value in drawdown.items()]
        return BacktestResult(
            id=str(uuid.uuid4()), request=request, metrics=metrics,
            equity_curve=equity_curve, drawdown_curve=drawdown_curve, trades=trade_list,
            benchmark_curve=[{"timestamp": i.isoformat(), "value": float(v)} for i, v in benchmark.items()],
            ledger={"cash": cash, "quantity": quantity, "final_equity": float(equity.iloc[-1]),
                "realized_pnl": sum(t.pnl or 0 for t in trade_list),
                "unrealized_pnl": quantity * float(close.iloc[-1]) - entry_total if quantity else 0.0},
        )

