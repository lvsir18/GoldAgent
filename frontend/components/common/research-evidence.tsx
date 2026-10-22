"use client";
import { useLanguage } from "@/i18n/language";
import { displayTime, limitationLabel, sourceLabel, toolLabel } from "@/lib/presentation";

type Evidence = { snapshots?: any[]; citations?: any[]; limitations?: string[] };
export function ResearchEvidence({ evidence, tools = [] }: { evidence?: Evidence; tools?: any[] }) {
  const { locale, text } = useLanguage();
  return <details className="mt-4 rounded-lg border border-line p-3 text-sm">
    <summary className="cursor-pointer text-gold">{text("参考来源与研究说明", "Sources and research notes")} · {evidence?.citations?.length ?? 0}</summary>
    <div className="mt-3 space-y-3">
      {tools.map((tool, i) => <p key={i} className="text-xs text-muted">{toolLabel(tool.tool, text)} · {tool.error ? text("未能获取，可稍后重试", "Unavailable; retry later") : text("已完成", "Completed")}</p>)}
      {evidence?.snapshots?.map((snapshot, i) => <p key={i} className="text-xs text-muted">{toolLabel(snapshot.tool, text)} · {sourceLabel(snapshot.metadata?.source, text)} · {displayTime(snapshot.metadata?.retrieved_at, locale)} {snapshot.metadata?.is_stale ? text("（较早数据）", "(older data)") : ""}</p>)}
      {evidence?.citations?.map((citation, i) => {
        const url = typeof citation.url === "string" && /^https?:\/\//i.test(citation.url) ? citation.url : undefined;
        return <div key={i}>{url ? <a href={url} target="_blank" rel="noreferrer" className="text-gold">{citation.title || text("阅读来源", "Read source")}</a> : <span>{citation.title || text("知识库文档", "Knowledge document")}{citation.page != null ? ` · ${text("页", "Page")} ${citation.page}` : ""}</span>}<p className="text-xs text-muted">{sourceLabel(citation.source, text)} {citation.published_at ? displayTime(citation.published_at, locale) : url ? text("发布时间待确认", "Publication time unconfirmed") : ""}</p></div>;
      })}
      {[...new Set(evidence?.limitations?.map(value => limitationLabel(value, text)))].map((value, i) => <p key={i} className="text-warning">{value}</p>)}
      {!tools.length && !evidence?.snapshots?.length && !evidence?.citations?.length && <p className="text-muted">{text("暂无可展示的参考来源。", "No reference sources to display yet.")}</p>}
    </div>
  </details>;
}
