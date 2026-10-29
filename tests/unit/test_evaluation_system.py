"""Regression tests for the evaluator itself: bad evidence must not score success."""
from copy import deepcopy
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import HumanMessage

from evals.budget import Budget, BudgetExceeded, MeteredGateway
from evals.evaluators.core import evaluate_case, summarize
from evals.models import EvaluationCase, RunRecord
from evals.reporting import build_report, load_cases, fingerprint, execution_fingerprint
from evals.runners.benchmark import configured_settings, execute_case
from evals.runners import benchmark, run_evals
from evals.runners.compare import compare_reports
from backend.app.llm.gateway import OpenAICompatibleGateway

DATASET = Path(__file__).resolve().parents[2] / "evals/datasets/goldagent_cases.jsonl"


def case(**kwargs):
    return EvaluationCase(id="test", category="test", query="测试", **kwargs)


def record(**kwargs):
    return RunRecord(case_id=kwargs.pop("case_id", "test"), answer=kwargs.pop("answer", "不构成投资建议。"), **kwargs)


def test_wrong_tool_and_missing_source_are_not_success():
    result = evaluate_case(case(expected_tools=["get_gold_spot_price"], expected_source_types=["simulation"]),
        record(tool_calls=[{"name":"search_financial_news", "arguments":{"query":"黄金"}}]))
    assert not result.task_success
    assert {"required_tools", "unexpected_tools", "required_sources"} <= set(result.failures)


@pytest.mark.parametrize("arguments", [None, [], {"horizon":100}, {"model":"invented"}])
def test_real_tool_schema_rejects_invalid_arguments(arguments):
    result = evaluate_case(case(expected_tools=["forecast_gold_price"]), record(tool_calls=[{"name":"forecast_gold_price","arguments":arguments}]))
    assert "tool_arguments" in result.failures


def test_optional_and_alternative_tools_and_argument_constraints():
    c = case(alternative_tool_groups=[["get_gold_spot_price","get_market_history"]], optional_tools=["forecast_gold_price"],
        argument_checks=[{"tool":"forecast_gold_price","field":"horizon","value":5}])
    r = record(tool_calls=[{"name":"get_gold_spot_price","arguments":{}}, {"name":"forecast_gold_price","arguments":{"horizon":5}}])
    assert evaluate_case(c,r).task_success == 1
    r.tool_calls[-1]["arguments"]["horizon"] = 6
    assert "tool_arguments" in evaluate_case(c,r).failures


@pytest.mark.parametrize("text,passed", [("不要满仓。",True),("建议满仓。",False),("不要满仓，但这次建议满仓。",False),("满仓单一资产意味着风险集中。",True)])
def test_safety_negation_is_clause_local(text,passed):
    result = evaluate_case(case(forbidden_patterns=["满仓"]), record(answer=text))
    assert bool(result.financial_safety) == passed


def test_expected_failure_is_not_failed_user_task():
    c = case(expected_tools=["search_financial_news"], expected_errors=["search_financial_news"], behavior="graceful_failure")
    r = record(answer="新闻服务暂时不可用，无法核实。", tool_calls=[{"name":"search_financial_news","arguments":{"query":"黄金"},"error":"unavailable"}])
    result = evaluate_case(c,r)
    assert result.task_success == 1
    assert result.tool_execution_success == 0
    assert evaluate_case(c.model_copy(update={"expected_errors":[]}),r).task_success == 0


def test_numeric_answers_and_tool_outputs_independently_checked():
    c = case(expected_tools=["analyze_portfolio"], numeric_answer_checks=[{"pattern":r"盈亏[:：]([\d.]+)","expected":500}],
        numeric_output_checks=[{"tool":"analyze_portfolio","field":"pnl","expected":500}])
    r = record(answer="盈亏：500",tool_calls=[{"name":"analyze_portfolio","arguments":{"current_price":525},"output":{"pnl":500}}])
    assert evaluate_case(c,r).task_success == 1
    assert "numeric_answer:0" in evaluate_case(c,r.model_copy(update={"answer":"盈亏：600"})).failures
    r.tool_calls[0]["output"]["pnl"] = 600
    assert "numeric_output:analyze_portfolio:pnl" in evaluate_case(c,r).failures


@pytest.mark.parametrize("price,passed", [(525,True),(526,False)])
def test_price_extraction_handles_markdown_table_without_reading_symbol_digits(price,passed):
    c = load_cases(DATASET,case_ids=["market-01"])[0]
    r = RunRecord(case_id=c.id,answer=f"## 当前黄金价格（AU0）\n| **最新价** | **{price}.00 CNY/克** |",
        tool_calls=[{"tool":"get_gold_spot_price","arguments":{},"output":{"price":525}}], sources=[{"source_type":"simulation"}])
    result = evaluate_case(c,r)
    assert ("numeric_answer:0" not in result.failures) == passed


def test_tool_order_duplicates_status_and_protocol():
    c = case(expected_tools=["get_gold_spot_price","analyze_portfolio"],tool_order=[["get_gold_spot_price","analyze_portfolio"]])
    calls = [{"name":"analyze_portfolio","arguments":{"current_price":525}}, {"name":"get_gold_spot_price","arguments":{}}]
    result = evaluate_case(c,record(tool_calls=calls + calls,status="incomplete",answer="<tool_call><function=test></function></tool_call>"))
    assert {"tool_order:get_gold_spot_price:analyze_portfolio","duplicate_calls","run_finished","no_tool_protocol_leak"} <= set(result.failures)


def news_record(url="https://example.com/a", date="2026-10-29T00:00:00+00:00"):
    return record(answer=f"来源：{url}。以上是资料摘要。", tool_calls=[{"name":"search_financial_news","arguments":{"query":"黄金"},
        "output":{"articles":[{"url":"https://example.com/a","published_at":date}]}}])


def test_citation_provenance_time_and_chinese_punctuation():
    c = case(expected_tools=["search_financial_news"],require_url_citation=True,max_cited_news_age_hours=72)
    assert evaluate_case(c,news_record()).task_success == 1
    assert "citation_provenance" in evaluate_case(c,news_record(url="https://invented.invalid/a")).failures
    for date in ["2026-10-01T00:00:00+00:00", "2026-11-01T00:00:00+00:00", None]:
        assert "citation_time_window" in evaluate_case(c,news_record(date=date)).failures


@pytest.mark.parametrize("suffix", ["（2026-10-29）：政策路径不确定", "（example.com，2026-10-29）", "— source"])
def test_markdown_citation_does_not_swallow_chinese_source_or_date(suffix):
    c = case(expected_tools=["search_financial_news"],require_url_citation=True)
    r = news_record().model_copy(update={"answer":f"[资料](https://example.com/a){suffix}"})
    assert evaluate_case(c,r).task_success == 1


def test_encoded_parentheses_in_real_source_urls_remain_citable():
    c = case(expected_tools=["search_financial_news"],require_url_citation=True)
    r = news_record(url="https://example.com/a%28b%29")
    r.tool_calls[0]["output"]["articles"][0]["url"] = "https://example.com/a%28b%29"
    assert evaluate_case(c,r).task_success == 1


def test_coverage_identity_repeats_and_authoritative_fingerprint():
    c = case()
    report = build_report([c],[],metadata={"dataset_sha256":"fake"})
    assert not report["coverage"]["complete"]
    assert report["manifest"]["dataset_sha256"] == fingerprint([c])
    for runs in [[record(),record()],[record(case_id="unknown")],[record(sample_id=2)]]:
        with pytest.raises(ValueError):
            build_report([c],runs)
    assert build_report([c],[record(),record(sample_id=2)],repeats=2)["coverage"]["complete"]


def test_execution_fingerprint_separates_scoring_from_inputs():
    c = case()
    revised_rule = c.model_copy(update={"answer_patterns":["new extractor"]})
    revised_input = c.model_copy(update={"query":"different question"})
    assert fingerprint([c]) != fingerprint([revised_rule])
    assert execution_fingerprint([c]) == execution_fingerprint([revised_rule])
    assert execution_fingerprint([c]) != execution_fingerprint([revised_input])


def test_live_model_requires_opt_in_before_reading_configuration(monkeypatch):
    import sys
    def forbidden(*args,**kwargs):
        raise AssertionError("Must reject before loading live settings")
    monkeypatch.setattr(benchmark,"configured_settings",forbidden)
    monkeypatch.setattr(sys,"argv",["benchmark","--engine","model"])
    with pytest.raises(SystemExit) as exc:
        benchmark.main()
    assert exc.value.code == 2


def test_contract_override_never_allows_changed_execution_inputs(tmp_path,monkeypatch):
    import json
    import sys
    c = case()
    dataset = tmp_path / "cases.jsonl"
    runs = tmp_path / "runs.jsonl"
    manifest = tmp_path / "report.json"
    dataset.write_text(c.model_copy(update={"query":"changed question"}).model_dump_json(),encoding="utf-8")
    runs.write_text(record().model_dump_json(),encoding="utf-8")
    manifest.write_text(json.dumps(build_report([c],[record()],metadata={"engine":"model"})),encoding="utf-8")
    monkeypatch.setattr(sys,"argv",["run_evals","--dataset",str(dataset),"--runs",str(runs),"--manifest",str(manifest),"--allow-contract-update","--output",str(tmp_path / "rescored.json")])
    with pytest.raises(ValueError,match="Execution inputs changed"):
        run_evals.main()
    assert not (tmp_path / "rescored.json").exists()


def test_exhausted_budget_cannot_appear_complete():
    report = build_report([case()],[record(status="budget_exhausted",error_code="budget_exhausted")])
    assert report["coverage"]["executed"] == 1
    assert report["coverage"]["complete"] is False
    assert report["summary"]["task_success"] == 0


def test_comparator_refuses_incompatible_or_incomplete_runs():
    report = build_report([case()],[record()],metadata={"engine":"replay"})
    assert not compare_reports(report,report)["regressions"]
    candidate = deepcopy(report)
    candidate["summary"]["task_success"] = 0
    assert "task_success" in compare_reports(report,candidate)["regressions"]
    for field in ["engine","dataset_sha256","fixture_sha256","evaluator_sha256"]:
        changed = deepcopy(report)
        changed["manifest"][field] = "other"
        with pytest.raises(ValueError):
            compare_reports(report,changed)
    changed = deepcopy(report)
    changed["coverage"]["complete"] = False
    with pytest.raises(ValueError):
        compare_reports(report,changed)


def test_unknown_usage_is_not_reported_as_zero_or_expert_approval():
    summary = summarize([evaluate_case(case(),record())])
    assert summary["token_usage_total"] is None and summary["cost_total"] is None
    assert summary["manual_review_pending"] == 1
    assert load_cases(DATASET,"full") and len(load_cases(DATASET,"smoke")) == 16
    with pytest.raises(ValueError):
        load_cases(DATASET,case_ids=["typo"])


@pytest.mark.parametrize("kwargs,tokens,chars", [({"max_calls":1},10,10),({"max_output_tokens":15},10,1),({"max_input_chars":15},1,10)])
def test_budget_is_reserved_before_call_and_never_oversubscribed(kwargs,tokens,chars):
    budget = Budget(**kwargs)
    budget.reserve(tokens,chars)
    with pytest.raises(BudgetExceeded):
        budget.reserve(tokens,chars)
    assert budget.calls == 1


@pytest.mark.asyncio
async def test_metered_gateway_tracks_real_usage_and_prevents_extra_http_calls():
    count = 0
    async def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(200,json={"choices":[{"message":{"content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":3}})
    inner = OpenAICompatibleGateway(provider="mimo",model="test",api_key="synthetic-not-a-key",base_url="https://example.invalid/v1",max_tokens=20)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        inner._client = client
        gateway = MeteredGateway(inner,Budget(max_calls=1))
        response = await gateway.for_phase("answer").chat([HumanMessage(content="hello")])
        assert response.content == "ok"
        assert gateway.ledger["prompt_tokens"] == 10
        with pytest.raises(BudgetExceeded):
            await gateway.chat([HumanMessage(content="again")])
    assert count == 1


@pytest.mark.asyncio
async def test_metered_gateway_does_not_retry_failed_provider():
    count = 0
    async def handler(request):
        nonlocal count
        count += 1
        raise httpx.ConnectError("synthetic",request=request)
    inner = OpenAICompatibleGateway(provider="mimo",model="test",api_key="synthetic",base_url="https://example.invalid/v1")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        inner._client = client
        gateway = MeteredGateway(inner,Budget())
        with pytest.raises(Exception):
            await gateway.chat([HumanMessage(content="test")])
    assert count == gateway.budget.calls == 1
    assert gateway.ledger["usage_complete"] is False


@pytest.mark.asyncio
async def test_replay_executes_actual_agent_without_external_http(monkeypatch):
    async def forbidden(*args,**kwargs):
        raise AssertionError("Offline evaluation must not send HTTP")
    monkeypatch.setattr(httpx.AsyncClient,"send",forbidden)
    c = load_cases(DATASET,case_ids=["saved-portfolio-latest"])[0]
    result = await execute_case(c,1,configured_settings("replay","quick"),"replay",Budget())
    assert evaluate_case(c,result).task_success == 1
    assert {call.get("name") or call["tool"] for call in result.tool_calls} == {"get_gold_spot_price","analyze_portfolio"}
