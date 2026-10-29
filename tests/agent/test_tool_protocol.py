"""Protocol regression tests use synthetic prices, never saved user holdings."""
import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from backend.app.agent.context import bounded_history
from backend.app.agent.graph import GoldAgentRuntime
from backend.app.llm.base import ChatResponse, ToolCall
from backend.app.tools.registry import ToolRegistry
from src.settings import AppSettings

LEAKED = '<tool_call><function=goldspot_query_gold_price><parameter=product_type>国内期货</parameter></function></tool_call>'


class Args(BaseModel):
    symbol: str = "AU0"


class ScriptedGateway:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    async def chat(self, messages, tools=None):
        self.requests.append((messages, tools))
        return next(self.responses)


def agent(responses, mode="quick", max_steps=6):
    executions = []

    async def price(symbol="AU0"):
        """Synthetic price for offline protocol tests."""
        executions.append(symbol)
        return {"price":500, "metadata":{"source":"fixture", "source_type":"simulation"}}

    gateway = ScriptedGateway(responses)
    tool = StructuredTool.from_function(coroutine=price, name="fixture_price", args_schema=Args)
    settings = AppSettings(agent={"research_mode":mode, "max_steps":max_steps})
    return GoldAgentRuntime(settings, gateway, ToolRegistry([tool])), gateway, executions


async def invoke(runtime):
    return await runtime.invoke(user_message="分析测试行情", user_id="fixture-user", session_id="fixture-session")


@pytest.mark.parametrize("mode", ["quick", "deep"])
async def test_textual_calls_are_repaired_not_executed_or_returned(mode):
    calls = [ToolCall(id="price", name="fixture_price", arguments={})]
    if mode == "deep":
        calls.append(ToolCall(id="done", name="complete_research", arguments={}))
    runtime, gateway, executed = agent([
        ChatResponse(content=LEAKED, completion_tokens=5),
        ChatResponse(tool_calls=calls, completion_tokens=7),
        ChatResponse(content="测试参考价格为500，不代表实时行情。", completion_tokens=9),
    ], mode)
    state = await invoke(runtime)
    assert state["status"] == "completed"
    assert state["current_step"] == len(gateway.requests) == 3
    assert state["usage"]["completion_tokens"] == 21
    assert executed == ["AU0"]
    assert len(state["tool_results"]) == 1
    assert "goldspot_" not in state["final_answer"] and "<tool_call>" not in state["final_answer"]
    assert state["performance"][0]["response_issue"] == "textual_tool_protocol"
    assert all("goldspot_" not in str(m.content) for m in gateway.requests[1][0])


async def test_truncated_plan_does_not_fall_through_to_unfounded_synthesis():
    runtime, gateway, executed = agent([
        ChatResponse(content="READY", finish_reason="length"),
        ChatResponse(content="READY", finish_reason="length"),
    ], "deep")
    state = await invoke(runtime)
    assert state["status"] == "incomplete"
    assert state["current_step"] == len(gateway.requests) == 2
    assert executed == []
    assert [item["phase"] for item in state["performance"]] == ["plan", "plan"]
    assert "未能正确完成" in state["final_answer"]


@pytest.mark.parametrize("bad", [
    ChatResponse(content=LEAKED),
    ChatResponse(tool_calls=[ToolCall(id="bad", name="goldspot_query_gold_price", arguments={})]),
    ChatResponse(tool_calls=[ToolCall(id="bad", name="fixture_price", arguments={"symbol":123})]),
    ChatResponse(tool_calls=[ToolCall(id="bad", name="fixture_price", arguments={})], finish_reason="length"),
    ChatResponse(protocol_error="invalid_tool_arguments"),
    ChatResponse(finish_reason="tool_calls"),
    ChatResponse(content=""),
])
async def test_repeated_bad_responses_are_bounded_and_never_execute_tools(bad):
    runtime, gateway, executed = agent([bad, bad])
    state = await invoke(runtime)
    assert state["status"] == "incomplete"
    assert executed == [] and not state["tool_results"]
    assert len(gateway.requests) == 2
    assert "goldspot_" not in state["final_answer"]


@pytest.mark.parametrize("mode", ["quick", "deep"])
async def test_repair_respects_model_call_budget(mode):
    runtime, gateway, executed = agent([ChatResponse(content=LEAKED)], mode, max_steps=1)
    state = await invoke(runtime)
    assert state["current_step"] == len(gateway.requests) == 1
    assert state["status"] in {"incomplete", "max_steps"}
    assert executed == []


async def test_bad_final_synthesis_retries_without_enabling_tools():
    calls = [ToolCall(id="p", name="fixture_price", arguments={}), ToolCall(id="d", name="complete_research", arguments={})]
    runtime, gateway, executed = agent([
        ChatResponse(tool_calls=calls),
        ChatResponse(content=LEAKED),
        ChatResponse(content="根据已取得的模拟行情，需谨慎看待短期波动。"),
    ], "deep")
    state = await invoke(runtime)
    assert state["status"] == "completed"
    assert executed == ["AU0"]
    assert gateway.requests[-1][1] == gateway.requests[-2][1] == []
    assert [item["phase"] for item in state["performance"]] == ["plan", "synthesize", "synthesize"]
    assert "goldspot_" not in state["final_answer"]


async def test_native_tools_during_synthesis_are_not_executed():
    runtime, gateway, executed = agent([
        ChatResponse(content="READY"),
        ChatResponse(tool_calls=[ToolCall(id="bad", name="fixture_price", arguments={})]),
        ChatResponse(content="缺少实时资料，暂不能判断。"),
    ], "deep")
    state = await invoke(runtime)
    assert state["status"] == "completed"
    assert executed == []
    assert state["performance"][1]["response_issue"] == "tools_during_synthesis"


def test_old_assistant_protocol_does_not_poison_future_context():
    history = [{"role":"user", "content":LEAKED}, {"role":"assistant", "content":LEAKED}]
    bounded = bounded_history(history)
    assert bounded[0]["content"] == LEAKED  # Do not rewrite user-authored questions.
    assert "goldspot_" not in bounded[1]["content"]
    assert "未执行的工具指令" in bounded[1]["content"]
    assert history[1]["content"] == LEAKED
