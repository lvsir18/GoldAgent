"use client";

import { useQuery } from "@tanstack/react-query";
import { marketApi } from "@/services/api/market";
import { ErrorState, LoadingState } from "@/components/common/async-state";
import { SourceBadge } from "@/components/common/source-badge";
import { GoldChart } from "@/components/charts/gold-chart";
import { useLanguage } from "@/i18n/language";
import { userError } from "@/lib/presentation";
import Link from "next/link";
import { portfolioApi } from "@/services/api/domain";

const fmt = (value?: number) => value == null ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;

export function Dashboard() {
  const { text } = useLanguage();
  const portfolio = useQuery({ queryKey: ["portfolio"], queryFn: portfolioApi.get });
  const query = useQuery({ queryKey: ["dashboard"], refetchInterval: 60_000, queryFn: async () => { const [summary, history, technical] = await Promise.all([marketApi.summary(), marketApi.history(), marketApi.indicators()]); return { summary, history, technical }; } });
  if (query.isLoading) return <LoadingState label={text("正在获取黄金行情", "Loading gold market data")}/>;
  if (query.isError || !query.data) return <ErrorState message={(query.error as Error)?.message ?? text("行情不可用", "Market data unavailable")} retry={() => query.refetch()}/>;
  const { summary, history, technical } = query.data;
  const sessionPoint = history.points.at(-1);
  const holdings = portfolio.data;
  const pnl = holdings?.grams > 0 ? (summary.price - holdings.average_cost) * holdings.grams : null;
  const trend = ({ uptrend: text("上行", "Uptrend"), downtrend: text("下行", "Downtrend"), consolidation: text("震荡", "Consolidation") } as Record<string,string>)[technical.trend] ?? text("趋势待确认", "Trend unconfirmed");
  return <div className="space-y-5"><div className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-sm text-muted">MARKET OVERVIEW</p><h1 className="text-3xl font-semibold">{text("黄金市场仪表盘", "Gold Market Dashboard")}</h1></div><SourceBadge source={summary.metadata}/></div>
    {summary.metadata.is_stale && <div className="rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm text-warning">{text("当前展示缓存或过期数据，请核对更新时间。", "Cached or stale data is being shown; check the retrieval time.")}</div>}
    <section className="card border-gold/30 p-5"><p className="text-xs text-gold">{text("今日黄金与我的风险", "Gold today & my risk")}</p><h2 className="mt-2 text-xl font-medium">{text("先看变化，再做研究", "Understand changes before researching")}</h2><p className="mt-3 text-sm leading-7 text-muted">{text("参考行情", "Reference quote")} AU0 ¥{summary.price.toFixed(2)}/g · {text("日变化", "Daily change")} {fmt(summary.change_1d_pct)} · {text("已完成日线趋势", "Completed-candle trend")} {trend}。{text("夜盘交易日可能不同于自然日期；数据时间以下方标注为准。", "Night-session trading dates may differ from calendar dates; see timestamps below.")}</p><div className="mt-4 grid gap-3 sm:grid-cols-2"><div className="rounded-lg bg-canvas p-4"><p className="text-xs text-muted">{text("我的持仓参考浮盈亏", "My indicative portfolio PnL")}</p><p className={`mt-2 text-xl ${pnl == null ? "text-muted" : pnl >= 0 ? "text-positive" : "text-negative"}`}>{pnl == null ? text("尚未录入持仓", "No saved holdings") : `¥${pnl.toFixed(2)}`}</p><p className="mt-2 text-xs text-muted">{text("按 AU0 参考价估算，不是积存金、实物金或具体产品的可成交报价。", "Estimated using AU0, not an executable quote for savings gold, physical gold or a specific product.")}</p>{portfolio.error && <p className="text-xs text-negative">{userError(portfolio.error, text)}</p>}</div><div className="flex flex-col justify-center gap-3 text-sm"><Link href={`/chat?q=${encodeURIComponent(text("请结合最新行情与72小时内新闻，简短说明今天黄金的变化、对已保存持仓的影响，以及需要继续跟踪的风险，引用来源。", "Give a concise gold brief using the latest quote, news in the last 72 hours and my saved holdings. Cite sources and risks."))}`} className="rounded-lg bg-gold px-4 py-3 text-center text-black">{text("开始今日研究 →", "Research today →")}</Link><Link href="/portfolio" className="text-center text-gold">{text("录入或更新持仓", "Add or update holdings")}</Link><Link href="/news" className="text-center text-muted">{text("查看最新新闻", "Latest news")}</Link></div></div></section>
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[[summary.is_realtime ? text("最新成交", "Latest trade") : text("上一收盘", "Previous close"), `¥${summary.price.toFixed(2)}/g`], [summary.change_basis === "previous_settlement" ? text("较昨结算", "vs prev. settlement") : text("较前收", "vs previous close"), fmt(summary.change_1d_pct)], [text("本周", "This week"), fmt(summary.change_1w_pct)], [text("本月", "This month"), fmt(summary.change_1m_pct)]].map(([label, value]) => <article key={label} className="card p-4"><p className="text-xs text-muted">{label}</p><p className="tabular mt-2 text-2xl font-medium">{value}</p></article>)}</section>
    <section className="card flex flex-wrap gap-x-6 gap-y-2 p-4 text-sm"><span><span className="text-muted">{text("交易日", "Trading date")}：</span>{summary.trading_date ?? "—"}</span><span><span className="text-muted">{text("行情时间", "Quote time")}：</span>{summary.quote_time ?? "—"}</span><span><span className="text-muted">{text("上一收盘", "Previous close")}：</span>{summary.previous_close == null ? "—" : `¥${summary.previous_close.toFixed(2)}/g`}</span><span><span className="text-muted">{text("上一结算", "Previous settlement")}：</span>{summary.previous_settlement == null ? "—" : `¥${summary.previous_settlement.toFixed(2)}/g`}</span></section>
    <section className="card p-4"><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h2 className="font-medium">{text("AU0 行情", "AU0 Market")}</h2><p className="mt-1 text-xs text-muted">{sessionPoint?.is_provisional ? text("金色 K 线为正在进行的夜盘/下一交易日行情，不参与下方技术指标计算。", "The gold candle is the in-progress night/next trading session and is excluded from the technical indicators below.") : text("仅显示已完成日线。", "Completed daily candles only.")}</p></div><span className="text-xs text-muted">{history.points.length} {text("条记录", "observations")}</span></div><GoldChart points={history.points}/></section>
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">{[["RSI", technical.rsi?.toFixed(2)], ["MACD", technical.macd?.toFixed(2)], [text("趋势", "Trend"), trend], [text("波动率", "Volatility"), technical.volatility == null ? undefined : `${(technical.volatility * 100).toFixed(2)}%`], [text("支撑", "Support"), technical.support?.toFixed(2)], [text("阻力", "Resistance"), technical.resistance?.toFixed(2)]].map(([label, value]) => <article key={label} className="card p-4"><p className="text-xs text-muted">{label}</p><p className="tabular mt-2 text-lg">{value ?? "—"}</p></article>)}</section>
  </div>;
}
