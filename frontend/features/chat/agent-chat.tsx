"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useLanguage } from "@/i18n/language";
import { streamChat, sessionsApi } from "@/services/api/chat";
import type { Session } from "@/types/api";
import { MarkdownContent } from "@/components/common/markdown-content";
import { reportsApi, researchApi } from "@/services/api/domain";
import Link from "next/link";

type Message = { role: "user" | "assistant"; content: string };
type Activity = { tool: string; success: boolean | null };
type ActivityNote = "idle" | "deciding" | "no-tools";

const toolNames: Record<string, [string, string]> = {
  get_gold_spot_price: ["获取黄金现价", "Gold spot price"],
  get_market_history: ["获取历史行情", "Market history"],
  calculate_technical_indicators: ["计算技术指标", "Technical indicators"],
  search_financial_news: ["搜索财经新闻", "Financial news"],
  forecast_gold_price: ["黄金价格预测", "Gold forecast"],
  analyze_portfolio: ["投资组合分析", "Portfolio analysis"],
  run_backtest: ["运行策略回测", "Strategy backtest"],
  retrieve_financial_knowledge: ["检索金融知识库", "Knowledge retrieval"],
};

export function AgentChat() {
  const { locale, text } = useLanguage();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [activityNote, setActivityNote] = useState<ActivityNote>("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [showActivity, setShowActivity] = useState(true);
  const [mode, setMode] = useState("quick");
  const [runId, setRunId] = useState("");
  const [evidence, setEvidence] = useState<any>(null);
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const viewport = useRef<HTMLDivElement>(null);
  const follow = useRef(true);
  const toolCount = useRef(0);

  const refresh = async () => setSessions(await sessionsApi.list());

  useEffect(() => {
    refresh().catch(error => setError(error.message));
    const draft = new URLSearchParams(window.location.search).get("q");
    if (draft) setInput(draft.slice(0, 10000));
    if (window.matchMedia("(max-width: 1023px)").matches) setShowActivity(false);
    return () => abort.current?.abort();
  }, []);
  useEffect(() => { if (follow.current && viewport.current) viewport.current.scrollTop = viewport.current.scrollHeight; }, [messages, progress]);

  const stageLabel = (stage: string) => {
    const labels: Record<string, [string, string]> = {
      load_context: ["正在准备会话上下文…", "Preparing conversation context…"],
      llm: ["模型正在规划或生成分析…", "The model is planning or generating analysis…"],
      llm_complete: ["模型响应完成，正在处理结果…", "Model response received; processing results…"],
      verify: ["正在核验数据来源和工具结果…", "Verifying sources and tool results…"],
      guardrail: ["正在应用金融风险护栏…", "Applying financial safety guardrails…"],
      waiting: ["仍在执行，请稍候…", "Still working; please wait…"],
    };
    const pair = labels[stage];
    return pair ? text(pair[0], pair[1]) : text("正在执行…", "Working…");
  };

  const toolLabel = (tool: string) => {
    const pair = toolNames[tool];
    return pair ? text(pair[0], pair[1]) : tool;
  };

  const select = async (id: string) => {
    if (busy) return;
    setSessionId(id);
    const history = await sessionsApi.messages(id);
    setMessages(history.map(message => ({ role: message.role as Message["role"], content: message.content })));
    setActivities([]);
    setRunId(""); setEvidence(null); setNotice("");
    setActivityNote("idle");
    setError(null);
  };

  const create = () => {
    if (busy) return;
    setSessionId(null);
    setMessages([]);
    setActivities([]);
    setRunId(""); setEvidence(null); setNotice("");
    setActivityNote("idle");
    setProgress("");
    setError(null);
    setInput("");
  };

  const remove = async (session: Session) => {
    if (busy) return;
    const confirmed = window.confirm(text(`删除会话“${session.title}”？`, `Delete “${session.title}”?`));
    if (!confirmed) return;
    await sessionsApi.remove(session.id);
    if (sessionId === session.id) create();
    await refresh();
  };

  const finishActivity = (tool: string, success: boolean) => {
    setActivities(old => {
      const copy = [...old];
      let index = -1;
      for (let i = copy.length - 1; i >= 0; i -= 1) {
        if (copy[i].tool === tool && copy[i].success === null) {
          index = i;
          break;
        }
      }
      if (index >= 0) copy[index] = { ...copy[index], success };
      else copy.push({ tool, success });
      return copy;
    });
  };

  const send = async (event: FormEvent) => {
    event.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    setInput("");
    setBusy(true);
    setProgress(text("正在启动 Agent…", "Starting Agent…"));
    setError(null);
    setRunId(""); setEvidence(null); setNotice("");
    follow.current = true;
    abort.current = new AbortController();
    setActivities([]);
    setActivityNote("deciding");
    toolCount.current = 0;
    setMessages(old => [...old, { role: "user", content: question }, { role: "assistant", content: "" }]);

    try {
      const activeSession = sessionId ?? (await sessionsApi.create()).id;
      setSessionId(activeSession);
      await streamChat(question, activeSession, (name, payload) => {
        if (name === "run_started") {
          setProgress(text("Agent 已开始执行…", "Agent run started…"));
        }
        if (name === "run_progress") {
          setProgress(stageLabel(String(payload.stage ?? "")));
        }
        if (name === "tool_started") {
          const tool = String(payload.tool);
          toolCount.current += 1;
          setActivityNote("idle");
          setProgress(text(`正在执行：${toolLabel(tool)}…`, `Running: ${toolLabel(tool)}…`));
          setActivities(old => [...old, { tool, success: null }]);
        }
        if (name === "tool_finished") {
          const tool = String(payload.tool);
          const success = Boolean(payload.success);
          setProgress(success
            ? text(`${toolLabel(tool)}已完成`, `${toolLabel(tool)} completed`)
            : text(`${toolLabel(tool)}执行失败`, `${toolLabel(tool)} failed`));
          finishActivity(tool, success);
        }
        if (name === "answer_delta") {
          setProgress(text("正在生成最终回答…", "Composing the final answer…"));
          setMessages(old => {
            const copy = [...old];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, content: last.content + String(payload.delta ?? "") };
            return copy;
          });
        }
        if (name === "run_finished") {
          setRunId(String(payload.run_id)); setEvidence(payload.evidence ?? null);
          if (toolCount.current === 0) setActivityNote("no-tools");
          setNotice(payload.status === "completed" ? text("研究已保存到任务记录", "Research saved to task history") : text("研究达到步数上限，结果不完整", "Step limit reached; research is incomplete"));
          setSessionId(String(payload.session_id));
          refresh().catch(error => setError(error.message));
        }
        if (name === "error") {
          setProgress("");
          setError(String(payload.message ?? text("Agent 执行失败", "Agent run failed")));
          refresh().catch(() => undefined);
        }
      }, { signal: abort.current!.signal, mode });
    } catch (error) {
      if ((error as Error).name === "AbortError") setNotice(text("已停止，可以修改问题后重试", "Stopped. Edit your question to retry."));
      else setError((error as Error).message);
    } finally {
      setBusy(false);
      setProgress("");
    }
  };

  return (
    <div className={`grid h-full min-h-0 gap-3 overflow-y-auto scrollbar-subtle lg:overflow-hidden ${showHistory && showActivity ? "lg:grid-cols-[220px_minmax(0,1fr)_250px]" : showHistory ? "lg:grid-cols-[220px_minmax(0,1fr)]" : showActivity ? "lg:grid-cols-[minmax(0,1fr)_250px]" : "lg:grid-cols-1"}`}>
      {showHistory && <aside className="card flex max-h-64 min-h-0 flex-col overflow-hidden lg:max-h-none">
        <div className="shrink-0 border-b border-line p-3">
          <button
            onClick={create}
            disabled={busy}
            className="focus-ring flex w-full items-center justify-center gap-2 rounded-lg bg-gold px-3 py-2 text-sm font-medium text-black disabled:opacity-50"
          >
            <MessageSquarePlus size={16}/>{text("新建会话", "New chat")}
          </button>
        </div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2 scrollbar-subtle">
          {sessions.length === 0 && <p className="px-3 py-4 text-center text-xs text-muted">{text("暂无历史会话", "No conversations yet")}</p>}
          {sessions.map(session => (
            <div key={session.id} className={`group flex items-center rounded-lg ${sessionId === session.id ? "bg-canvas" : "hover:bg-canvas"}`}>
              <button
                onClick={() => select(session.id)}
                className={`min-w-0 flex-1 truncate px-3 py-2.5 text-left text-sm ${sessionId === session.id ? "text-gold" : "text-muted group-hover:text-ink"}`}
                title={session.title}
              >
                {locale === "en" && session.title === "新会话" ? "New chat" : session.title}
              </button>
              <button
                onClick={() => remove(session)}
                className="focus-ring mr-1 rounded-md p-2 text-muted opacity-70 hover:bg-negative/10 hover:text-negative lg:opacity-0 lg:group-hover:opacity-100"
                aria-label={text(`删除会话：${session.title}`, `Delete conversation: ${session.title}`)}
                title={text("删除会话", "Delete conversation")}
              >
                <Trash2 size={15}/>
              </button>
            </div>
          ))}
        </div>
      </aside>}

      <section className="card flex min-h-[520px] min-w-0 flex-col overflow-hidden lg:min-h-0">
        <div className="shrink-0 border-b border-line px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><h1 className="font-medium">{text("黄金研究助手", "Gold Research Agent")}</h1><div className="flex flex-wrap gap-3 text-xs text-gold"><button onClick={() => setShowHistory(v => !v)} aria-expanded={showHistory}>{text("会话历史", "History")}</button><button onClick={create} disabled={busy}>{text("新会话", "New chat")}</button><button onClick={() => setShowActivity(v => !v)} aria-expanded={showActivity}>{text("执行详情", "Activity")}</button><Link href="/tasks">{text("任务记录", "Tasks")}</Link></div></div>
          <p className="text-xs text-muted">{text("工具结果会经过来源核验和金融护栏", "Tool results are source-checked and passed through financial guardrails")}</p>
        </div>
        <div ref={viewport} onScroll={e => { const el = e.currentTarget; follow.current = el.scrollHeight - el.scrollTop - el.clientHeight < 100; }} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 scrollbar-subtle sm:p-5">
          {messages.length === 0 && (
            <div className="mx-auto mt-[8vh] max-w-2xl text-center text-muted">
              <p className="text-lg text-ink">{text("从一个真实任务开始", "Start with a real task")}</p>
              <p className="mt-2 text-sm">{text("例如：结合当前行情和最近美联储新闻分析黄金，并说明数据来源。", "For example: Analyze gold using current prices and recent Fed news, and cite the data sources.")}</p>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">{[["今日简报", "Morning brief", "请用简短晨报梳理黄金最新行情和72小时内关键新闻，区分事实、推测与风险并引用来源。"], ["持仓风险", "Portfolio risk", "结合已保存持仓和风险偏好分析当前黄金风险。缺少资料时先说明，不提供自动交易指令。"], ["事件解读", "Event analysis", "检索最近72小时美联储相关新闻，分析对黄金的影响，列出相反情景和可核查来源。"], ["研报问答", "Knowledge Q&A", "检索我的知识库中有关实际利率与黄金的资料，标注文档、页码；没有相关资料则明确说明。"]].map(([zh,en,prompt]) => <button key={zh} onClick={() => setInput(locale === "zh" ? prompt : `Please complete this research task in English: ${prompt}`)} className="rounded-xl border border-line p-4 text-left text-sm text-ink hover:border-gold">{text(zh,en)}<span className="mt-1 block text-xs text-muted">{text("点击填入问题，可编辑后发送", "Click to draft, then edit and send")}</span></button>)}</div>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`max-w-full rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "ml-auto w-fit max-w-[88%] whitespace-pre-wrap bg-gold text-black" : "w-full bg-canvas"}`}>
              {message.role === "assistant" && message.content
                ? <MarkdownContent content={message.content}/>
                : message.content || (busy ? progress || text("正在执行…", "Working…") : "")}
              {message.role === "assistant" && message.content && !busy && <button className="mt-3 block text-xs text-gold" onClick={() => navigator.clipboard.writeText(message.content).then(() => setNotice(text("已复制", "Copied"))).catch(e => setError(e.message))}>{text("复制回答", "Copy answer")}</button>}
            </div>
          ))}
          {evidence && <details className="rounded-lg border border-line p-3 text-sm"><summary className="cursor-pointer text-gold">{text("证据与数据边界", "Evidence and limitations")} · {evidence.citations?.length ?? 0}</summary><div className="mt-3 space-y-3">{evidence.snapshots?.map((s: any, i: number) => <p key={i} className="text-xs text-muted">{s.tool} · {s.metadata.source} · {s.metadata.retrieved_at} {s.metadata.is_stale ? text("（过期）", "(stale)") : ""}</p>)}{evidence.citations?.map((c: any, i: number) => <p key={i}>{c.url ? <a href={c.url} target="_blank" rel="noreferrer" className="text-gold">{c.title}</a> : `${c.title} · ${text("页", "page")} ${c.page ?? "—"} · ${c.chunk_id}`}<span className="block text-xs text-muted">{c.source} {c.published_at}</span></p>)}{evidence.limitations?.map((s: string, i: number) => <p key={i} className="text-warning">{s}</p>)}</div></details>}
          {runId && !busy && <div className="flex flex-wrap gap-4 text-xs text-gold"><button disabled={saving} onClick={async () => { setSaving(true); try { await reportsApi.create({ title: messages.findLast(m => m.role === "user")?.content.slice(0, 60) || "Gold research", run_id: runId }); setNotice(text("报告已保存，可到报告库查看", "Saved to report library")); } catch (e) { setError((e as Error).message); } finally { setSaving(false); } }}>{text("保存研究报告", "Save report")}</button><button onClick={() => researchApi.feedback(runId, "helpful").then(() => setNotice(text("已记录反馈", "Feedback saved"))).catch(e => setError(e.message))}>{text("有帮助", "Helpful")}</button><button onClick={() => researchApi.feedback(runId, "unhelpful").then(() => setNotice(text("已记录反馈", "Feedback saved"))).catch(e => setError(e.message))}>{text("需改进", "Needs improvement")}</button></div>}
          {notice && <p role="status" className="text-xs text-gold">{notice}</p>}
        </div>
        <form onSubmit={send} className="shrink-0 border-t border-line bg-surface p-3 sm:p-4">
          <div className="mb-2 flex flex-wrap items-center gap-3 text-xs text-muted"><select aria-label={text("研究模式", "Research mode")} value={mode} onChange={e => setMode(e.target.value)} disabled={busy} className="rounded border border-line bg-canvas p-1"><option value="quick">{text("快速问答 · 最多4轮", "Quick · up to 4 rounds")}</option><option value="deep">{text("深入研究 · 配置预算", "Deep · configured budget")}</option></select><span>{text("仅显示执行事实；最终回答经核验后呈现", "Execution facts only; final answer appears after verification")}</span>{messages.length > 0 && !busy && <button type="button" onClick={() => setInput([...messages].reverse().find(m => m.role === "user")?.content ?? "")} className="text-gold">{text("编辑上个问题重试", "Edit last question to retry")}</button>}</div>
          <div className="mx-auto flex w-full max-w-4xl items-end gap-2">
            <textarea
              value={input}
              onChange={event => setInput(event.target.value)}
              onKeyDown={event => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              rows={1}
              className="focus-ring max-h-40 min-h-12 flex-1 resize-y rounded-xl border border-line bg-canvas p-3 text-sm"
              placeholder={text("询问行情、新闻、预测、持仓或回测…", "Ask about prices, news, forecasts, portfolios, or backtests…")}
            />
            <button disabled={busy || !input.trim()} className="focus-ring h-12 rounded-xl bg-gold px-5 text-sm font-medium text-black disabled:opacity-50">
              {busy ? text("执行中", "Running") : text("发送", "Send")}
            </button>
            {busy && <button type="button" onClick={() => abort.current?.abort()} className="h-12 rounded-xl border border-negative/50 px-3 text-sm text-negative">{text("停止", "Stop")}</button>}
          </div>
        </form>
        {error && <div className="shrink-0 border-t border-negative/40 p-3 text-sm text-negative">{error}</div>}
      </section>

      {showActivity && <aside className="card max-h-80 min-h-0 overflow-y-auto p-4 scrollbar-subtle lg:max-h-none">
        <h2 className="text-sm font-medium">Agent Activity</h2>
        <p className="mt-1 text-xs leading-5 text-muted">
          {text("不显示隐藏推理，只显示当前阶段和工具执行事实。", "Hidden reasoning is not shown; only stages and actual tool executions are displayed.")}
        </p>
        {busy && progress && <div className="mt-4 rounded-lg border border-gold/30 bg-gold/5 p-3 text-sm text-gold">{progress}</div>}
        <div className="mt-4 space-y-2">
          {activities.map((activity, index) => (
            <div key={`${activity.tool}-${index}`} className="rounded-lg border border-line p-3 text-sm">
              <div>{toolLabel(activity.tool)}</div>
              <div className={activity.success === null ? "text-warning" : activity.success ? "text-positive" : "text-negative"}>
                {activity.success === null ? text("执行中", "Running") : activity.success ? text("已完成", "Completed") : text("失败", "Failed")}
              </div>
            </div>
          ))}
          {activities.length === 0 && activityNote === "deciding" && <p className="text-sm text-muted">{text("Agent 正在判断是否需要调用工具…", "The Agent is deciding whether tools are needed…")}</p>}
          {activities.length === 0 && activityNote === "no-tools" && <p className="rounded-lg border border-line p-3 text-sm text-muted">{text("本次回答未调用工具，由模型直接生成。", "No tools were used for this response; it was generated directly by the model.")}</p>}
          {activities.length === 0 && activityNote === "idle" && <p className="text-sm text-muted">{text("发送问题后将在这里显示工具调用。", "Tool calls will appear here after you send a question.")}</p>}
        </div>
      </aside>}
    </div>
  );
}
