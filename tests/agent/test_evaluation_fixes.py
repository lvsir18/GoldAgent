"""Production improvements motivated by the frozen first evaluation baseline."""
from pathlib import Path

import pytest
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from backend.app.agent.evidence import append_news_evidence
from backend.app.agent.graph import GoldAgentRuntime
from backend.app.agent.prompts import build_system_prompt
from backend.app.llm.base import ChatResponse, ToolCall
from backend.app.llm.gateway import OpenAICompatibleGateway
from backend.app.tools.registry import ToolRegistry
from evals.fixtures import fixture_tools
from evals.reporting import load_cases
from src.settings import AppSettings


def article(url="https://example.com/news", **changes):
    return {"url":url,"title":"Test report","source":"Example","published_at":"2026-10-29T00:00:00Z",**changes}


def news_results(articles, **changes):
    return [{"tool":"search_financial_news","output":{"articles":articles},**changes}]


def test_news_fallback_uses_real_references_once_with_publication_time():
    records = news_results([article()])
    answer,flags = append_news_evidence("消息影响存在不确定性。", records)
    assert "https://example.com/news" in answer
    assert "2026-10-29T00:00:00Z" in answer
    assert "不代表每条均支持" in answer
    assert flags == ["news_reference_appendix_added"]
    again,flags = append_news_evidence(answer, records)
    assert again == answer and flags == []
    assert records[0]["output"]["articles"][0]["title"] == "Test report"


def test_cited_answer_keeps_model_selected_evidence_without_extra_references():
    answer = "资料来源：[原文](https://example.com/news)。"
    result,flags = append_news_evidence(answer,news_results([article(),article(url="https://example.com/unused")]))
    assert result == answer and not flags


def test_auto_language_fallback_follows_an_english_answer():
    result,_ = append_news_evidence("Policy remains uncertain.",news_results([article()]))
    assert "Retrieved references" in result and "本次检索资料" not in result


def test_prefix_of_an_invented_link_does_not_suppress_real_source_fallback():
    result,flags = append_news_evidence("https://example.com/news-invented",news_results([article()]))
    assert flags == ["news_reference_appendix_added"]
    assert "[Test report](https://example.com/news)" in result


def test_markdown_url_followed_by_chinese_date_is_not_duplicated():
    answer = "[资料](https://example.com/news)（2026-10-29）：政策路径不明。"
    result,flags = append_news_evidence(answer,news_results([article()]))
    assert result == answer and not flags


@pytest.mark.parametrize("url", [None,"javascript:alert(1)","https://user:password@example.com/a","https://example.com/a\nmalicious","https://[invalid"])
def test_news_fallback_never_constructs_links_from_unsafe_or_missing_urls(url):
    answer,flags = append_news_evidence("无法核实。",news_results([article(url=url)]))
    assert answer == "无法核实。" and flags == []


def test_failed_news_never_produces_a_fake_citation():
    result,flags = append_news_evidence("新闻暂不可用。", news_results([article()],error="failure"))
    assert result == "新闻暂不可用。" and not flags


def test_fallback_is_bounded_deduplicated_escaped_and_has_no_invented_date():
    records = news_results([article(title="[bad](javascript:alert(1))\n#header",published_at=None,retrieved_at="2099-01-01")]
        + [article()] + [article(url=f"https://example.com/{i}") for i in range(5)])
    answer,_ = append_news_evidence("Summary",records,language="en")
    assert answer.count("\n- [") == 3
    assert "publication time unavailable" in answer
    assert "2099-01-01" not in answer
    assert "[bad]" not in answer and "\n#header" not in answer


class Args(BaseModel):
    query: str = "gold"


class PhaseGateway:
    def __init__(self):
        self.requests = []

    def for_phase(self,phase):
        owner = self
        class Phase:
            async def chat(self,messages,tools=None):
                owner.requests.append((phase,tools))
                if len(owner.requests) == 1:
                    return ChatResponse(tool_calls=[ToolCall(id="news",name="search_financial_news",arguments={"query":"gold"})])
                return ChatResponse(content="新闻资料显示政策路径不确定，不能承诺金价方向。")
        return Phase()


@pytest.mark.parametrize("steps,last_phase", [(2,"quick_synthesize"),(4,"quick")])
async def test_quick_evidence_fallback_adds_no_model_request_and_reserves_final_step(steps,last_phase):
    async def news(query="gold"):
        return {"articles":[article()]}
    gateway = PhaseGateway()
    tool = StructuredTool.from_function(coroutine=news,name="search_financial_news",description="Synthetic news",args_schema=Args)
    agent = GoldAgentRuntime(AppSettings(agent={"research_mode":"quick","max_steps":steps}),gateway,ToolRegistry([tool]))
    state = await agent.invoke(user_message="消息影响",user_id="synthetic",session_id="test")
    assert [phase for phase,_ in gateway.requests] == ["quick",last_phase]
    assert len(gateway.requests) == state["current_step"] == 2
    if last_phase == "quick_synthesize":
        assert gateway.requests[-1][1] == []
    assert state["status"] == "completed"
    assert "https://example.com/news" in state["final_answer"]
    assert state["verification_result"]["evidence_flags"] == ["news_reference_appendix_added"]


@pytest.mark.parametrize("phase", ["quick","quick_synthesize"])
def test_quick_mimo_budget_disables_reasoning_without_raising_output_limit(phase):
    gateway = OpenAICompatibleGateway(provider="mimo",model="synthetic",api_key="synthetic",base_url="https://example.invalid",max_tokens=1600)
    request = gateway.for_phase(phase)._payload([],[])
    assert request["thinking"] == {"type":"disabled"}
    assert request["max_completion_tokens"] == 1600
    assert gateway.for_phase("synthesize")._payload([],[])["thinking"] == {"type":"enabled"}


def test_prompt_distinguishes_explicit_input_minimal_tools_and_financial_meanings():
    prompt = build_system_prompt(portfolio_context={"grams":20,"average_cost":500})
    for instruction in ["当轮用户明确提供", "无需查询实时行情或知识库", "先简短澄清", "不擅自用行情覆盖", "可点击 URL", "浮动/未实现盈亏", "不是未来价格的正负区间", "完整文件名（含扩展名）", "不插入未经查询"]:
        assert instruction in prompt
    assert "仅在当前任务需要时使用" in prompt


async def test_tool_evidence_marks_unrealized_pnl_and_historical_error_interpretation():
    dataset = Path(__file__).resolve().parents[2] / "evals/datasets/goldagent_cases.jsonl"
    case = load_cases(dataset,case_ids=["portfolio-01"])[0]
    tools = fixture_tools(case,AppSettings())
    holding = await tools.get("analyze_portfolio").ainvoke({"current_price":650,"grams":20,"average_cost":600})
    assert holding["pnl"] == 1000
    assert holding["pnl_type"] == "unrealized" and holding["realized_pnl_available"] is False
    forecast = await tools.get("forecast_gold_price").ainvoke({"period":"3mo","model":"linear","horizon":3})
    assert forecast["interpretation"]["confidence_interval_available"] is False
    assert "NOT" in tools.get("forecast_gold_price").description
