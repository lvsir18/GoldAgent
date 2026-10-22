import json
import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from backend.app.agent.graph import GoldAgentRuntime
from backend.app.agent.context import tool_context, bounded_history
from backend.app.llm.base import ChatResponse, ToolCall
from backend.app.tools.registry import ToolRegistry
from src.settings import AppSettings


class Args(BaseModel):
    symbol: str = "AU0"


class StagedGateway:
    def __init__(self, repeat=False):
        self.phases = []
        self.repeat = repeat

    def for_phase(self, phase):
        parent = self
        class Call:
            async def chat(self, messages, tools=None):
                parent.phases.append(phase)
                if phase == "synthesize":
                    assert tools == []
                    assert all(m.content != "READY" for m in messages)
                    return ChatResponse(content="假设价格为520，以下为离线分析。", reasoning_content="PRIVATE_REASONING", completion_tokens=20, reasoning_tokens=5)
                if parent.repeat or not any(isinstance(m, ToolMessage) for m in messages):
                    return ChatResponse(tool_calls=[ToolCall(id=str(len(parent.phases)),name="fixture",arguments={"symbol":"AU0"})])
                return ChatResponse(content="READY")
        return Call()


async def fixture(symbol="AU0"):
    return {"price":520,"symbol":symbol,"metadata":{"source":"offline","source_type":"simulation"}}


def runtime(gateway, max_steps=12):
    tools = [StructuredTool.from_function(coroutine=fixture,name="fixture",description="offline fixture",args_schema=Args)]
    return GoldAgentRuntime(AppSettings(agent={"research_mode":"deep","max_steps":max_steps}),gateway,ToolRegistry(tools))


@pytest.mark.parametrize("repeat", [False, True])
async def test_deep_research_reasons_only_during_final_synthesis(repeat):
    gateway = StagedGateway(repeat)
    state = await runtime(gateway).invoke(user_message="分析黄金",user_id="u",session_id="s")
    assert gateway.phases == ["plan", "plan", "synthesize"]
    assert state["current_step"] == 3
    assert state["status"] == "completed"
    assert state["usage"]["reasoning_tokens"] == 5
    assert "PRIVATE_REASONING" not in state["final_answer"]
    assert "不构成投资建议" in state["final_answer"]
    assert [p["phase"] for p in state["performance"]] == gateway.phases


async def test_deep_research_reserves_final_call_without_exceeding_budget():
    gateway = StagedGateway()
    state = await runtime(gateway, max_steps=2).invoke(user_message="分析黄金",user_id="u",session_id="s")
    assert gateway.phases == ["plan", "synthesize"]
    assert state["status"] == "max_steps"
    assert state["current_step"] == 2


def test_backtest_context_is_small_but_original_evidence_and_metrics_are_intact():
    output = {"metrics":{"maximum_drawdown":-0.2},"ledger":{"cash":120},
        "equity_curve":[{"timestamp":str(i),"value":i} for i in range(1000)],
        "trades":[{"price":i,"quantity":2} for i in range(200)]}
    raw = json.dumps(output,ensure_ascii=False)
    compact = tool_context("run_backtest", output)
    view = json.loads(compact)
    assert len(compact) < len(raw) * 0.1
    assert view["metrics"] == output["metrics"]
    assert view["ledger"] == output["ledger"]
    assert view["equity_curve"][0] == output["equity_curve"][0]
    assert view["equity_curve"][-1] == output["equity_curve"][-1]
    assert view["context_limits"]["trades"]["original_count"] == 200
    assert len(output["equity_curve"]) == 1000
    assert len(output["trades"]) == 200


def test_news_compaction_keeps_citable_source_and_marks_truncation():
    output = {"articles":[{"title":"Test", "summary":"a"*800,"url":"https://example.com/news","published_at":"2026-10-22","source":"fixture"}]}
    article = json.loads(tool_context("search_financial_news",output))["articles"][0]
    assert article["url"] == output["articles"][0]["url"]
    assert article["published_at"] == "2026-10-22"
    assert article["summary_truncated"]
    assert len(output["articles"][0]["summary"]) == 800


def test_history_budget_keeps_latest_messages_without_mutating_history():
    history = [{"role":"user","content":"A"*20000},{"role":"assistant","content":"B"*10000},{"role":"user","content":"latest"}]
    result = bounded_history(history)
    assert sum(len(i["content"]) for i in result) <= 24000
    assert result[-1]["content"] == "latest"
    assert len(history) == 3


async def test_completion_signal_saves_a_model_round_without_skipping_evidence():
    class BatchedGateway(StagedGateway):
        def for_phase(self, phase):
            parent = self
            fallback = super().for_phase(phase)
            class Call:
                async def chat(self, messages, tools=None):
                    if phase == "plan":
                        parent.phases.append(phase)
                        assert "complete_research" in [t.name for t in tools]
                        return ChatResponse(tool_calls=[ToolCall(id="price",name="fixture",arguments={}),ToolCall(id="done",name="complete_research",arguments={})])
                    assert any(isinstance(m,ToolMessage) and '"price":520' in m.content for m in messages)
                    return await fallback.chat(messages,tools)
            return Call()
    gateway = BatchedGateway()
    state = await runtime(gateway).invoke(user_message="分析黄金",user_id="u",session_id="s")
    assert gateway.phases == ["plan", "synthesize"]
    assert state["status"] == "completed"
    assert len(state["tool_results"]) == 1
    assert state["tool_results"][0]["output"]["price"] == 520


async def test_truncated_model_output_is_not_marked_completed():
    class LimitedGateway:
        async def chat(self,messages,tools=None):
            return ChatResponse(content="partial",finish_reason="length")
    agent = GoldAgentRuntime(AppSettings(),LimitedGateway(),ToolRegistry([]))
    state = await agent.invoke(user_message="test",user_id="u",session_id="s")
    assert state["status"] == "incomplete"
    assert "未完整完成" in state["final_answer"]
