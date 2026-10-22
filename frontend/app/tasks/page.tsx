"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { researchApi, reportsApi } from "@/services/api/domain";
import { ResearchEvidence } from "@/components/common/research-evidence";
import { MarkdownContent } from "@/components/common/markdown-content";
import { PageHeading } from "@/components/common/page-heading";
import { useLanguage } from "@/i18n/language";
import { userError } from "@/lib/presentation";

export default function TasksPage() {
  const { locale, text } = useLanguage();
  const [selected, setSelected] = useState("");
  const [notice, setNotice] = useState("");
  const list = useQuery({ queryKey: ["research-runs"], queryFn: researchApi.list, refetchInterval: 5000 });
  const detail = useQuery({ queryKey: ["research-run", selected], queryFn: () => researchApi.get(selected), enabled: Boolean(selected), refetchInterval: q => q.state.data?.status === "running" ? 3000 : false });
  const status: Record<string,string> = { running: text("执行中", "Running"), completed: text("已完成", "Completed"), failed: text("失败", "Failed"), cancelled: text("已停止", "Stopped"), max_steps: text("研究暂未完成", "Research unfinished"), incomplete: text("结果未完整生成", "Incomplete response") };
  return <div className="space-y-4"><PageHeading eyebrow="RESEARCH HISTORY" title={text("研究任务记录", "Research task history")} description={text("查看研究进度、结论和参考资料；未完成时可编辑问题重新发起。", "Review research progress, conclusions and references. Edit and retry unfinished questions.")}/>
    {(list.error || detail.error) && <p role="alert" className="text-negative">{userError(list.error || detail.error, text)}</p>}
    {list.isLoading && <p>{text("加载中…", "Loading…")}</p>}
    {list.data?.length === 0 && <p className="card p-8 text-center text-muted">{text("还没有研究任务，先从今日简报开始。", "No tasks yet. Start with a morning brief.")} <Link href="/chat" className="text-gold">{text("开始研究", "Start research")}</Link></p>}
    <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]"><div className="space-y-2">{list.data?.map(run => <button key={run.id} onClick={() => { setSelected(run.id); setNotice(""); }} className={`card w-full p-4 text-left ${run.id === selected ? "border-gold" : ""}`}><p className="line-clamp-2 text-sm">{run.question || text("研究任务", "Research task")}</p><p className="mt-2 text-xs text-muted">{status[run.status] || text("状态更新中", "Updating status")} · {new Date(run.created_at).toLocaleString(locale === "zh" ? "zh-CN" : "en-US")}</p></button>)}</div>
    {detail.data && <section className="card min-w-0 overflow-hidden p-5"><div className="mb-4 flex flex-wrap gap-4 text-sm text-gold"><span>{status[detail.data.status] || text("状态更新中", "Updating status")}</span>{detail.data.state?.question && <Link href={`/chat?q=${encodeURIComponent(detail.data.state.question)}`}>{text("编辑并重新研究", "Edit and research again")}</Link>}{detail.data.status === "completed" && <button onClick={() => reportsApi.create({ title: detail.data.state.question?.slice(0, 80) || "Research", run_id: selected }).then(() => setNotice(text("已保存到报告库", "Saved to reports"))).catch(e => setNotice(userError(e, text)))}>{text("保存报告", "Save report")}</button>}</div>{notice && <p role="status" className="mb-3 text-sm text-gold">{notice}</p>}{detail.data.error && <p className="text-negative">{userError(detail.data.error, text)}</p>}<MarkdownContent content={detail.data.state?.final_answer || text("任务尚无最终结果", "No final result yet")}/><ResearchEvidence evidence={detail.data.state?.evidence} tools={detail.data.state?.tool_results}/></section>}
    </div></div>;
}
