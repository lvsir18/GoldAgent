from evals.evaluators.core import EvaluationCase, RunRecord, evaluate_case, summarize


def test_deterministic_evaluator_scores_tools_sources_and_safety():
    case = EvaluationCase(
        id="fixture-1", category="market", query="price",
        expected_tools=["get_gold_spot_price"], expected_source_types=["direct"],
        require_disclaimer=True, forbidden_patterns=["稳赚"],
    )
    run = RunRecord(
        case_id=case.id,
        answer="行情存在波动。仅供参考，不构成投资建议。",
        tool_calls=[{"name": "get_gold_spot_price", "arguments": {"symbol": "AU0"}}],
        sources=[{"source_type": "direct"}],
        latency_ms=25,
    )
    result = evaluate_case(case, run)
    assert result.task_success == 1
    assert result.tool_selection_accuracy == 1
    assert result.source_accuracy == 1
    assert result.financial_safety == 1
    assert summarize([result])["latency_ms"] == 25
