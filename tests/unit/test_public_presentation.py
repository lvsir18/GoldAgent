from datetime import datetime, timezone
from types import SimpleNamespace
from backend.app.agent.guardrails import apply_financial_guardrail, verify_tool_results
from backend.app.services.research import research_evidence
from backend.app.services.reports import ReportService
from backend.app.api.routes.reports import public_content

DIAGNOSTIC = "ValidationError Traceback postgres://private-host INTERNAL_CANARY"


def test_legacy_tool_markup_does_not_leak_through_reports_or_guardrails():
    from backend.app.core.presentation import public_answer
    leaked = '<tool_call><function=goldspot_query_gold_price><parameter=product_type>国内期货</parameter></function></tool_call>'
    for value in [leaked, leaked.replace("<", "&lt;").replace(">", "&gt;"), '<tool_call><function=goldspot_query_gold_price']:
        content = public_answer(value + "\n仅供参考。")
        assert "goldspot_" not in content and "<tool_call>" not in content
        assert "未执行的工具指令" in content
    report = ReportService().render_markdown("analysis", "fixture", {"final_answer":leaked})
    assert "goldspot_" not in report and "未执行的工具指令" in report
    answer, flags = apply_financial_guardrail(leaked, None, False)
    assert "goldspot_" not in answer and "invalid_tool_protocol" in flags


def test_failed_tools_keep_details_out_of_answer_and_evidence():
    results = [{"tool":"get_market_history", "error":DIAGNOSTIC, "arguments":{"context":"PRIVATE_ARGUMENT_CANARY"}}]
    verification = verify_tool_results(results)
    assert verification["passed"] is False
    answer, _ = apply_financial_guardrail("资料不足，暂不判断方向。", verification, False)
    assert "历史行情暂时获取失败" in answer
    assert "INTERNAL_CANARY" not in answer
    assert "get_market_history" not in answer
    assert DIAGNOSTIC not in str(research_evidence(results))
    assert results[0]["error"] == DIAGNOSTIC  # Private diagnostic record is untouched.


def test_reports_allowlist_facts_and_migrate_old_content():
    payload = {
        "run_id":"PRIVATE_RUN_CANARY", "session_id":"PRIVATE_SESSION_CANARY",
        "question":"黄金走势如何？", "final_answer":f"保持谨慎。\n\n数据说明：get_market_history failed: {DIAGNOSTIC}",
        "messages":[{"content":"PRIVATE_CONTEXT_CANARY"}],
        "tool_results":[{"tool":"get_market_history", "error":DIAGNOSTIC, "arguments":{"private":"PRIVATE_ARGUMENT_CANARY"}}],
        "evidence":{"citations":[{"title":"央行公告", "url":"https://example.com/gold", "source":"央行", "published_at":"2026-10-22"}, {"title":"研报.md","chunk_id":"PRIVATE_CHUNK_CANARY", "page":2}], "limitations":[DIAGNOSTIC]},
    }
    created = datetime(2026, 10, 22, tzinfo=timezone.utc)
    old_report = SimpleNamespace(report_type="analysis", title="研究", metadata_json=payload, created_at=created, content=DIAGNOSTIC)
    content = public_content(old_report)
    assert content == ReportService().render_markdown("analysis", "研究", payload, created)
    assert "## 研究结论" in content and "保持谨慎" in content
    assert "https://example.com/gold" in content and "页码：2" in content
    assert "CANARY" not in content and "ValidationError" not in content
    assert "```json" not in content and "tool_results" not in content


def test_market_snapshot_preserves_price_unit_source_and_limits():
    content = ReportService().render_markdown("analysis", "行情", {"market_snapshot":{"price":525, "metadata":{"source":"Derived from AkShare AU0 and USD/CNY", "currency":"USD/oz", "is_derived":True, "is_stale":True, "retrieved_at":"2026-10-22T10:00:00Z"}}})
    assert "525" in content and "美元/盎司" in content
    assert "换算" in content and "较早" in content
    assert "未查询外部资料" not in content
