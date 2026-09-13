"use client";

import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { backtestApi } from "@/services/api/domain";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";

type MetricDefinition = {
  label: [string, string];
  format: "percent" | "number" | "integer" | "currency";
};

const metricDefinitions: Record<string, MetricDefinition> = {
  cumulative_return: { label: ["累计收益率", "Cumulative return"], format: "percent" },
  annualized_return: { label: ["年化收益率", "Annualized return"], format: "percent" },
  maximum_drawdown: { label: ["最大回撤", "Maximum drawdown"], format: "percent" },
  sharpe_ratio: { label: ["夏普比率", "Sharpe ratio"], format: "number" },
  win_rate: { label: ["胜率", "Win rate"], format: "percent" },
  trade_count: { label: ["交易次数", "Trade count"], format: "integer" },
  turnover: { label: ["累计换手", "Turnover"], format: "number" },
  transaction_cost: { label: ["交易成本", "Transaction cost"], format: "currency" },
  benchmark_return: { label: ["买入持有收益率", "Buy-and-hold return"], format: "percent" },
};

const statusLabels: Record<string, [string, string]> = {
  queued: ["排队中", "Queued"],
  running: ["运行中", "Running"],
  completed: ["已完成", "Completed"],
  failed: ["失败", "Failed"],
};

export default function BacktestPage() {
  const { text } = useLanguage();
  const [id, setId] = useState<string | null>(null);
  const [shortWindow, setShortWindow] = useState(5);
  const [longWindow, setLongWindow] = useState(20);
  const create = useMutation({
    mutationFn: () => backtestApi.create({
      strategy: "ma_cross",
      initial_capital: 100000,
      transaction_cost_rate: 0.0015,
      parameters: { short_window: shortWindow, long_window: longWindow },
    }),
    onSuccess: data => setId(data.id),
  });
  const result = useQuery({
    queryKey: ["backtest", id],
    queryFn: () => backtestApi.get(id!),
    enabled: Boolean(id),
    refetchInterval: query => ["completed", "failed"].includes(query.state.data?.status) ? false : 1500,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const backtest = result.data?.result;
  const status = result.data?.status ?? create.data?.status ?? "queued";

  const formatMetric = (key: string, value: unknown) => {
    if (typeof value !== "number") return String(value);
    const definition = metricDefinitions[key];
    if (definition?.format === "percent") return `${(value * 100).toFixed(2)}%`;
    if (definition?.format === "integer") return value.toFixed(0);
    if (definition?.format === "currency") return `¥${value.toFixed(2)}`;
    return value.toFixed(2);
  };

  return (
    <div>
      <PageHeading
        eyebrow="NO LOOK-AHEAD"
        title={text("策略回测", "Strategy Backtest")}
        description={text("信号在下一周期执行，并计入交易成本；结果与买入持有基准对比。", "Signals execute in the next period with transaction costs and are compared against buy-and-hold.")}
      />
      <form onSubmit={submit} className="card flex flex-wrap items-end gap-4 p-5">
        <label className="text-sm">{text("短均线", "Short MA")}
          <input type="number" min={2} value={shortWindow} onChange={event => setShortWindow(Number(event.target.value))} className="focus-ring mt-2 block w-28 rounded border border-line bg-canvas p-2" />
        </label>
        <label className="text-sm">{text("长均线", "Long MA")}
          <input type="number" min={3} value={longWindow} onChange={event => setLongWindow(Number(event.target.value))} className="focus-ring mt-2 block w-28 rounded border border-line bg-canvas p-2" />
        </label>
        <button disabled={create.isPending || shortWindow >= longWindow} className="focus-ring rounded bg-gold px-5 py-2 text-black disabled:opacity-40">
          {create.isPending ? text("正在创建…", "Creating…") : text("运行回测", "Run backtest")}
        </button>
        {shortWindow >= longWindow && <span className="text-sm text-negative">{text("短均线必须小于长均线", "Short MA must be less than long MA")}</span>}
      </form>

      {id && <p className="my-4 text-sm text-muted">{text("任务", "Job")} {id} · {text(...(statusLabels[status] ?? [status, status]))}</p>}
      {(create.error || result.data?.error) && <p className="text-negative">{create.error?.message ?? result.data?.error}</p>}

      {backtest && (
        <div>
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Object.entries(backtest.metrics).map(([key, value]) => {
              const definition = metricDefinitions[key];
              return <Metric key={key} label={definition ? text(...definition.label) : key} value={formatMetric(key, value)} />;
            })}
          </section>
          <section className="card mt-4 overflow-x-auto p-4">
            <h2 className="mb-3 font-medium">{text("交易记录", "Trades")}</h2>
            {backtest.trades.length === 0 ? (
              <p className="text-sm text-muted">{text("当前参数下没有产生交易。", "No trades were generated with these parameters.")}</p>
            ) : (
              <table className="w-full text-left text-sm">
                <thead className="text-muted"><tr><th>{text("时间", "Time")}</th><th>{text("动作", "Action")}</th><th>{text("价格", "Price")}</th><th>{text("数量", "Quantity")}</th><th>{text("成本", "Cost")}</th><th>{text("盈亏", "PnL")}</th></tr></thead>
                <tbody>{backtest.trades.map((trade: any, index: number) => (
                  <tr key={index} className="border-t border-line">
                    <td className="py-2">{trade.timestamp.slice(0, 10)}</td>
                    <td>{trade.action === "buy" ? text("买入", "Buy") : trade.action === "sell" ? text("卖出", "Sell") : trade.action}</td>
                    <td>{trade.price.toFixed(2)}</td>
                    <td>{trade.quantity.toFixed(4)}</td>
                    <td>{trade.cost.toFixed(2)}</td>
                    <td>{trade.pnl?.toFixed(2) ?? "—"}</td>
                  </tr>
                ))}</tbody>
              </table>
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="card p-4"><div className="text-xs text-muted">{label}</div><div className="tabular mt-2 text-xl">{value}</div></div>;
}
