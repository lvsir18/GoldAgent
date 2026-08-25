from __future__ import annotations

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from backend.app.agent.graph import GoldAgentRuntime
from backend.app.llm.base import ChatResponse, ToolCall
from backend.app.tools.registry import ToolRegistry
from src.settings import AppSettings


class PriceArgs(BaseModel):
    symbol: str = "AU0"


async def fixture_price(symbol: str = "AU0"):
    return {"price": 520.0, "symbol": symbol, "metadata": {"source_type": "direct", "is_stale": False}}


class TwoStepGateway:
    def __init__(self):
        self.calls = 0

    async def chat(self, messages, tools=None):
        self.calls += 1
        if not any(isinstance(message, ToolMessage) for message in messages):
            return ChatResponse(tool_calls=[ToolCall(id="call-1", name="fixture_price", arguments={"symbol": "AU0"})])
        return ChatResponse(content="当前测试金价为 520 元/克。")


async def test_agent_routes_tool_verifies_and_applies_guardrail():
    tool = StructuredTool.from_function(
        coroutine=fixture_price,
        name="fixture_price",
        description="Return an offline fixture price",
        args_schema=PriceArgs,
    )
    gateway = TwoStepGateway()
    runtime = GoldAgentRuntime(AppSettings(agent={"max_steps": 3, "max_tool_retries": 0}), gateway, ToolRegistry([tool]))
    events = []

    async def capture(event, payload):
        events.append((event, payload))

    state = await runtime.invoke(
        user_message="现在金价多少？", user_id="user-1", session_id="session-1",
        on_event=capture,
    )
    assert gateway.calls == 2
    assert state["tool_results"][0]["output"]["price"] == 520
    assert state["verification_result"]["passed"]
    assert "不构成投资建议" in state["final_answer"]
    assert any(event == "tool_started" for event, _ in events)
    assert any(event == "tool_finished" for event, _ in events)
    assert any(event == "run_progress" for event, _ in events)


async def test_agent_stops_at_max_steps_and_stream_starts_immediately():
    tool = StructuredTool.from_function(coroutine=fixture_price, name="fixture_price", description="fixture", args_schema=PriceArgs)
    runtime = GoldAgentRuntime(AppSettings(agent={"max_steps": 1, "max_tool_retries": 0}), TwoStepGateway(), ToolRegistry([tool]))
    iterator = runtime.events(user_message="price", user_id="user-1", session_id="session-max")
    first = await anext(iterator)
    assert first["event"] == "run_started"
    remaining = [event async for event in iterator]
    assert remaining[-1]["event"] == "run_finished"
    assert remaining[-1]["status"] == "completed"
