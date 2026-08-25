"use client";

import type { SourceMetadata } from "@/types/api";
import { useLanguage } from "@/i18n/language";

export function SourceBadge({ source }: { source: SourceMetadata }) {
  const { locale, text } = useLanguage();
  const freshness = source.is_stale ? text("已过期", "Stale") : source.is_cached ? text("缓存", "Cached") : text("当前", "Current");
  return <details className="relative inline-block"><summary className="cursor-pointer list-none rounded-full border border-line px-2 py-1 text-xs text-muted">{source.source_type === "derived" ? text("推导", "Derived") : source.source} · {freshness}</summary><div className="absolute right-0 z-10 mt-2 w-max max-w-xs rounded-lg border border-line bg-surface p-3 text-xs shadow-xl"><div>{source.source}</div><div className="mt-1 text-muted">{text("获取", "Retrieved")}: {new Date(source.retrieved_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</div><div className="text-muted">{text("范围", "Range")}: {source.data_start?.slice(0, 10)} — {source.data_end?.slice(0, 10)}</div><div className="text-muted">{source.symbol} · {source.market} · {source.currency}</div></div></details>;
}
