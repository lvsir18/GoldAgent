"use client";

import { displayTime, sourceLabel } from "@/lib/presentation";
import type { SourceMetadata } from "@/types/api";
import { useLanguage } from "@/i18n/language";

export function SourceBadge({ source }: { source: SourceMetadata }) {
  const { locale, text } = useLanguage();
  const currency = source.currency?.split("/")[0];
  const freshness = source.is_stale ? text("已过期", "Stale") : source.is_cached ? text("已保存行情", "Saved market data") : text("本次获取", "Retrieved");
  return <details className="relative inline-block"><summary className="cursor-pointer list-none rounded-full border border-line px-2 py-1 text-xs text-muted">{source.source_type === "derived" ? text("推导", "Derived") : sourceLabel(source.source, text)} · {freshness}</summary><div className="absolute right-0 z-10 mt-2 w-max max-w-xs rounded-lg border border-line bg-surface p-3 text-xs shadow-xl"><div>{sourceLabel(source.source, text)}</div><div className="mt-1 text-muted">{text("获取", "Retrieved")}: {displayTime(source.retrieved_at, locale)}</div><div className="text-muted">{text("范围", "Range")}: {source.data_start?.slice(0, 10)} — {source.data_end?.slice(0, 10)}</div><div className="text-muted">{source.symbol} · {source.market === "CN" ? text("国内市场", "Domestic market") : text("国际市场", "International market")} · {currency === "CNY" ? text("人民币", "CNY") : currency === "USD" ? text("美元", "USD") : text("计价单位待确认", "Currency unconfirmed")}</div></div></details>;
}
