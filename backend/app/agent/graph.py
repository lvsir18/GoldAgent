"""LangGraph supervisor with iterative structured-tool execution."""

from __future__ import annotations

import asyncio
import json
import uuid
import time
from typing import Any, AsyncIterator, Awaitable, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.settings import AppSettings

from ..llm.base import LLMGateway
from ..llm.gateway import build_llm_gateway
from ..tools.registry import ToolRegistry, build_tool_registry
from .guardrails import apply_financial_guardrail, verify_tool_results
from .prompts import build_system_prompt
from .state import GoldAgentState

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class GoldAgentRuntime:
    def __init__(self, settings: AppSettings, gateway: LLMGateway, tools: ToolRegistry, checkpointer=None):
        self.settings = settings
        self.gateway = gateway
        self.tools = tools
        self._progress_callback: ProgressCallback | None = None
        self.graph = self._build_graph(checkpointer or MemorySaver())

    async def _emit(self, event: str, **payload: Any) -> None:
        if self._progress_callback is not None:
            await self._progress_callback(event, payload)

    def _build_graph(self, checkpointer):
        builder = StateGraph(GoldAgentState)
        builder.add_node("load_context", self._load_context)
        builder.add_node("supervisor", self._supervisor)
        builder.add_node("execute_tools", self._execute_tools)
        builder.add_node("verify_results", self._verify_results)
        builder.add_node("financial_guardrail", self._financial_guardrail)
        builder.add_node("save_memory", self._save_memory)
        builder.add_edge(START, "load_context")
        builder.add_edge("load_context", "supervisor")
        builder.add_conditional_edges(
            "supervisor", self._after_supervisor,
            {"tools": "execute_tools", "verify": "verify_results"},
        )
        builder.add_edge("execute_tools", "supervisor")
        builder.add_edge("verify_results", "financial_guardrail")
        builder.add_edge("financial_guardrail", "save_memory")
        builder.add_edge("save_memory", END)
        return builder.compile(checkpointer=checkpointer)

    async def _load_context(self, state: GoldAgentState) -> dict[str, Any]:
        await self._emit("run_progress", stage="load_context", message="正在准备会话上下文…")
        messages = state.get("messages", [])
        system_prompt = build_system_prompt(
            state.get("user_preferences"), state.get("risk_profile"), state.get("portfolio_context"),
        )
        messages = [SystemMessage(content=system_prompt), *[m for m in messages if not isinstance(m, SystemMessage)]]
        return {
            "messages": messages,
            "run_id": state.get("run_id") or str(uuid.uuid4()),
            "tool_results": state.get("tool_results", []),
            "current_step": state.get("current_step", 0),
            "max_steps": state.get("max_steps", self.settings.agent.max_steps),
            "retry_count": state.get("retry_count", 0),
            "status": "running",
        }

    async def _supervisor(self, state: GoldAgentState) -> dict[str, Any]:
        if state.get("current_step", 0) >= state.get("max_steps", self.settings.agent.max_steps):
            return {"messages": [*state["messages"], AIMessage(content="已达到最大工具执行步数，当前研究未完整完成，请缩小问题范围后重试。")], "status": "max_steps"}
        step = state.get("current_step", 0) + 1
        await self._emit("run_progress", stage="llm", step=step, message="模型正在规划或生成分析…")
        response = await self.gateway.chat(state["messages"], self.tools.tools)
        await self._emit("run_progress", stage="llm_complete", step=step, message="模型响应完成，正在处理结果…")
        tool_calls = [
            {"id": call.id, "name": call.name, "args": call.arguments, "type": "tool_call"}
            for call in response.tool_calls
        ]
        return {
            "messages": [*state["messages"], AIMessage(content=response.content, tool_calls=tool_calls)],
            "current_step": state.get("current_step", 0) + 1,
            "usage": {"prompt_tokens": state.get("usage", {}).get("prompt_tokens", 0) + (response.prompt_tokens or 0), "completion_tokens": state.get("usage", {}).get("completion_tokens", 0) + (response.completion_tokens or 0)},
        }

    def _after_supervisor(self, state: GoldAgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "verify"

    async def _execute_tools(self, state: GoldAgentState) -> dict[str, Any]:
        last = state["messages"][-1]
        readonly = {"get_gold_spot_price", "get_market_history", "calculate_technical_indicators", "search_financial_news", "forecast_gold_price", "analyze_portfolio", "run_backtest", "retrieve_financial_knowledge"}
        calls = getattr(last, "tool_calls", [])
        # Unknown extensions are executed serially until explicitly classified.
        semaphore = asyncio.Semaphore(3 if all(c["name"] in readonly for c in calls) else 1)

        async def execute(call):
            async with semaphore:
                return await self._execute_one(call)

        results = await asyncio.gather(*(execute(call) for call in calls))
        return {"messages": [*state["messages"], *[r[0] for r in results]],
            "tool_results": [*state.get("tool_results", []), *[r[1] for r in results]]}

    async def _execute_one(self, call):
        name, args, call_id = call["name"], call.get("args", {}), call.get("id") or str(uuid.uuid4())
        started = time.perf_counter()
        await self._emit("tool_started", tool=name, message=f"正在执行工具：{name}")
        try:
            output = None
            for attempt in range(self.settings.agent.max_tool_retries + 1):
                try:
                    output = await self.tools.get(name).ainvoke(args)
                    break
                except Exception:
                    if attempt >= self.settings.agent.max_tool_retries:
                        raise
            observation = {"tool": name, "arguments": args, "output": output, "error": None, "duration_ms": (time.perf_counter()-started)*1000}
            content = json.dumps(output, ensure_ascii=False, default=str)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            observation = {"tool": name, "arguments": args, "output": None, "error": error, "duration_ms": (time.perf_counter()-started)*1000}
            content = json.dumps({"success": False, "error": error}, ensure_ascii=False)
        await self._emit(
            "tool_finished", tool=name, success=not bool(observation.get("error")),
            duration_ms=observation.get("duration_ms"),
            message=f"工具 {name} 已完成" if not observation.get("error") else f"工具 {name} 执行失败",
        )
        return ToolMessage(content=content, tool_call_id=call_id, name=name), observation

    async def _verify_results(self, state: GoldAgentState) -> dict[str, Any]:
        await self._emit("run_progress", stage="verify", message="正在核验数据来源和工具结果…")
        verification = verify_tool_results(state.get("tool_results", []))
        last_ai = next((m for m in reversed(state["messages"]) if isinstance(m, AIMessage) and m.content), None)
        return {"verification_result": verification, "final_answer": str(last_ai.content) if last_ai else "暂时无法生成回答。"}

    async def _financial_guardrail(self, state: GoldAgentState) -> dict[str, Any]:
        await self._emit("run_progress", stage="guardrail", message="正在应用金融风险护栏…")
        portfolio = state.get("portfolio_context") or {}
        answer, flags = apply_financial_guardrail(
            state.get("final_answer") or "暂时无法生成回答。",
            state.get("verification_result"),
            float(portfolio.get("grams", 0) or 0) > 0,
        )
        verification = dict(state.get("verification_result") or {})
        verification["guardrail_flags"] = flags
        return {"final_answer": answer, "verification_result": verification}

    async def _save_memory(self, state: GoldAgentState) -> dict[str, Any]:
        return {"status": "max_steps" if state.get("status") == "max_steps" else "completed"}

    async def invoke(
        self, *, user_message: str, user_id: str, session_id: str,
        run_id: str | None = None, on_event: ProgressCallback | None = None,
        portfolio_context: dict[str, Any] | None = None,
        user_preferences: dict[str, Any] | None = None,
        risk_profile: dict[str, Any] | None = None,
        history: list[dict[str, str]] | None = None,
        max_steps: int | None = None,
    ) -> GoldAgentState:
        resolved_run_id = run_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": f"{user_id}:{session_id}"}}
        if history is None:
            previous = await self.graph.aget_state(config)
            messages = list(previous.values.get("messages", [])) if previous.values else []
        else:
            messages = [HumanMessage(content=m["content"]) if m["role"] == "user" else AIMessage(content=m["content"]) for m in history[-30:] if m["role"] in {"user", "assistant"}]
        state: GoldAgentState = {
            "messages": [*messages, HumanMessage(content=user_message)], "user_id": user_id,
            "session_id": session_id, "run_id": resolved_run_id,
            "tool_results": [], "current_step": 0, "max_steps": max_steps or self.settings.agent.max_steps,
            "retry_count": 0, "status": "created", "usage": {}, "portfolio_context": portfolio_context,
            "user_preferences": user_preferences, "risk_profile": risk_profile,
        }
        # API calls supply tenant-scoped committed conversation history explicitly;
        # current preferences and holdings replace, rather than append to, context.
        self._progress_callback = on_event
        try:
            async with asyncio.timeout(self.settings.agent.run_timeout_seconds):
                return await self.graph.ainvoke(state, config=config)
        except TimeoutError as exc:
            raise TimeoutError(
                f"Agent run exceeded the {self.settings.agent.run_timeout_seconds}s total timeout"
            ) from exc
        finally:
            self._progress_callback = None

    async def events(self, **kwargs) -> AsyncIterator[dict[str, Any]]:
        run_id = kwargs.get("run_id") or str(uuid.uuid4())
        kwargs["run_id"] = run_id
        yield {"event": "run_started", "run_id": run_id}
        state = await self.invoke(**kwargs)
        for result in state.get("tool_results", []):
            yield {"event": "tool_finished", "run_id": state["run_id"], "tool": result["tool"], "success": not bool(result.get("error"))}
        answer = state.get("final_answer", "")
        for offset in range(0, len(answer), 48):
            yield {"event": "answer_delta", "run_id": state["run_id"], "delta": answer[offset:offset + 48]}
        yield {"event": "run_finished", "run_id": state["run_id"], "status": state.get("status")}


def build_agent_runtime(settings: AppSettings, gateway: LLMGateway | None = None, tools: ToolRegistry | None = None, checkpointer=None) -> GoldAgentRuntime:
    return GoldAgentRuntime(
        settings=settings, gateway=gateway or build_llm_gateway(settings),
        tools=tools or build_tool_registry(), checkpointer=checkpointer,
    )
