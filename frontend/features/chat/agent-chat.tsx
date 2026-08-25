"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import { useLanguage } from "@/i18n/language";
import { streamChat, sessionsApi } from "@/services/api/chat";
import type { Session } from "@/types/api";

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
  const toolCount = useRef(0);

  const refresh = async () => setSessions(await sessionsApi.list());

  useEffect(() => {
    refresh().catch(error => setError(error.message));
  }, []);

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
    setActivityNote("idle");
    setError(null);
  };

  const create = () => {
    if (busy) return;
    setSessionId(null);
    setMessages([]);
    setActivities([]);
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
    setActivities([]);
    setActivityNote("deciding");
    toolCount.current = 0;
    setMessages(old => [...old, { role: "user", content: question }, { role: "assistant", content: "" }]);

    try {
      await streamChat(question, sessionId, (name, payload) => {
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
          if (toolCount.current === 0) setActivityNote("no-tools");
          setProgress(text("分析完成", "Analysis complete"));
          setSessionId(String(payload.session_id));
          refresh().catch(error => setError(error.message));
        }
        if (name === "error") {
          setProgress("");
          setError(String(payload.message ?? text("Agent 执行失败", "Agent run failed")));
          refresh().catch(() => undefined);
        }
      });
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setBusy(false);
      setProgress("");
    }
  };

  return (
    <div className="grid h-full min-h-0 gap-3 overflow-y-auto scrollbar-subtle lg:grid-cols-[260px_minmax(0,1fr)_280px] lg:overflow-hidden">
      <aside className="card flex max-h-64 min-h-0 flex-col overflow-hidden lg:max-h-none">
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
      </aside>

      <section className="card flex min-h-[520px] min-w-0 flex-col overflow-hidden lg:min-h-0">
        <div className="shrink-0 border-b border-line px-4 py-3">
          <h1 className="font-medium">Gold Supervisor Agent</h1>
          <p className="text-xs text-muted">{text("工具结果会经过来源核验和金融护栏", "Tool results are source-checked and passed through financial guardrails")}</p>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 scrollbar-subtle sm:p-5">
          {messages.length === 0 && (
            <div className="mx-auto mt-[18vh] max-w-md text-center text-muted">
              <p className="text-lg text-ink">{text("从一个真实任务开始", "Start with a real task")}</p>
              <p className="mt-2 text-sm">{text("例如：结合当前行情和最近美联储新闻分析黄金，并说明数据来源。", "For example: Analyze gold using current prices and recent Fed news, and cite the data sources.")}</p>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={index} className={`w-fit max-w-[88%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-6 sm:max-w-[min(82%,52rem)] ${message.role === "user" ? "ml-auto bg-gold text-black" : "bg-canvas"}`}>
              {message.content || (busy ? progress || text("正在执行…", "Working…") : "")}
            </div>
          ))}
        </div>
        <form onSubmit={send} className="shrink-0 border-t border-line bg-surface p-3 sm:p-4">
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
          </div>
        </form>
        {error && <div className="shrink-0 border-t border-negative/40 p-3 text-sm text-negative">{error}</div>}
      </section>

      <aside className="card max-h-80 min-h-0 overflow-y-auto p-4 scrollbar-subtle lg:max-h-none">
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
      </aside>
    </div>
  );
}
