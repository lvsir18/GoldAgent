"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { reportsApi, researchApi } from "@/services/api/domain";
import { downloadFile } from "@/services/api/client";
import { MarkdownContent } from "@/components/common/markdown-content";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";
import { userError } from "@/lib/presentation";

export default function ReportsPage() {
  const { locale, text } = useLanguage();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [runId, setRunId] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [error, setError] = useState("");
  const q = useQuery({ queryKey: ["reports"], queryFn: reportsApi.list });
  const runs = useQuery({ queryKey: ["research-runs"], queryFn: researchApi.list });
  const create = useMutation({ mutationFn: () => reportsApi.create({ title: title.trim() || text("黄金研究记录", "Gold research"), ...(runId ? { run_id: runId } : {}) }), onSuccess: data => { setPreview(data); qc.invalidateQueries({ queryKey: ["reports"] }); } });
  const remove = useMutation({ mutationFn: reportsApi.remove, onSuccess: (_, id) => { if (preview?.id === id) setPreview(null); qc.invalidateQueries({ queryKey: ["reports"] }); } });
  return <div className="space-y-4">
    <PageHeading eyebrow="RESEARCH LIBRARY" title={text("研究报告库", "Research library")} description={text("保存研究结论与引用来源，方便回顾和下载；也可单独保存当前行情快照。", "Save research conclusions and sources for review and download, or save a current market snapshot.")}/>
    <div className="card flex flex-wrap gap-3 p-4">
      <input aria-label={text("报告标题", "Report title")} placeholder={text("报告标题（可选）", "Report title (optional)")} value={title} onChange={e => setTitle(e.target.value)} className="min-w-0 flex-1 rounded border border-line bg-canvas p-2"/>
      <select aria-label={text("选择研究", "Select research")} value={runId} onChange={e => setRunId(e.target.value)} className="max-w-full rounded border border-line bg-canvas p-2"><option value="">{text("当前行情快照", "Current market snapshot")}</option>{runs.data?.filter(r => r.status === "completed").map(r => <option value={r.id} key={r.id}>{r.question || r.created_at}</option>)}</select>
      <button disabled={create.isPending} onClick={() => create.mutate()} className="rounded bg-gold px-4 py-2 text-black disabled:opacity-50">{create.isPending ? text("正在保存…", "Saving…") : text("保存报告", "Save report")}</button>
    </div>
    {(q.error || create.error || remove.error || error) && <p role="alert" className="text-negative">{userError(error || q.error || create.error || remove.error, text)}</p>}
    {q.isLoading && <p>{text("加载中…", "Loading…")}</p>}
    {q.data?.length === 0 && <p className="card p-8 text-center text-muted">{text("暂无报告。在 Agent 中完成一次研究后即可保存。", "No reports yet. Complete a research task in Agent Chat to save one.")}</p>}
    {q.data?.map(r => <article key={r.id} className="card flex flex-wrap items-center justify-between gap-3 p-4"><div><h2>{r.title}</h2><time className="text-xs text-muted">{new Date(r.created_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</time></div><div className="flex gap-3"><button onClick={() => reportsApi.get(r.id).then(setPreview).catch(e => setError(e.message))} className="text-gold">{text("预览", "Preview")}</button><button onClick={() => downloadFile(`/reports/${r.id}/download`, `${r.title.replace(/[\\/:*?"<>|]/g, "_")}.md`).catch(e => setError(e.message))}>{text("下载", "Download")}</button><button onClick={() => { if (window.confirm(text("删除这份报告？", "Delete this report?"))) remove.mutate(r.id); }} className="text-negative">{text("删除", "Delete")}</button></div></article>)}
    {preview && <section className="card min-w-0 overflow-hidden p-5"><div className="mb-3 flex justify-between"><h2>{text("报告预览", "Report preview")}</h2><button onClick={() => setPreview(null)}>{text("关闭", "Close")}</button></div><MarkdownContent content={preview.content}/></section>}
  </div>;
}
