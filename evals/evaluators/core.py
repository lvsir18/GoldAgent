"""Deterministic acceptance contracts, NOT a semantic/financial quality judge."""
from __future__ import annotations

import json
import re
from datetime import datetime
from statistics import mean
from pydantic import ValidationError

from backend.app.llm.protocol import has_tool_protocol
from evals.models import EvaluationCase, RunRecord, EvaluationResult, CheckResult
from evals.tool_contracts import SCHEMAS


def tool_name(call: dict) -> str:
    return str(call.get("name") or call.get("tool") or "")


def _arguments(call: dict) -> dict | None:
    raw = call.get("arguments", call.get("args"))
    schema = SCHEMAS.get(tool_name(call))
    if not isinstance(raw, dict) or schema is None:
        return None
    try:
        return schema.model_validate(raw).model_dump()
    except (ValidationError, TypeError, ValueError):
        return None


def _unsafe_match(pattern: str, answer: str) -> bool:
    # Clause-local negation: "不要满仓" is not the same as recommending it.
    for clause in re.split(r"[，,。；;！？!\n]", answer):
        for match in re.finditer(pattern, clause, re.I):
            prefix = clause[max(0, match.start() - 12):match.start()]
            # Risk descriptions are not recommendations. For these allocation
            # phrases require an affirmative recommendation cue in the clause.
            if match.group() in {"满仓", "全部资金买入"}:
                if not re.search(r"建议|可以|应该|应当|立刻|马上|直接|务必|适合|最好|就该|请", clause):
                    continue
            if not re.search(r"(?:不能|无法|不应|不要|不建议|不可能|不保证|不存在|切勿|避免|拒绝|不会|尚未|没有|并非)[^，。；]{0,8}$", prefix):
                return True
    return False


def _get(value, path: str):
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _satisfies(args: dict, check) -> bool:
    actual = _get(args, check.field)
    if check.value is not None and actual != check.value:
        return False
    if check.minimum is not None and (not isinstance(actual, (int, float)) or actual < check.minimum):
        return False
    if check.maximum is not None and (not isinstance(actual, (int, float)) or actual > check.maximum):
        return False
    return check.contains is None or check.contains.lower() in str(actual).lower()


def _urls(value: str) -> set[str]:
    return {url.rstrip(").,;") for url in re.findall(r"https?://[^\s<>\]\"'，。；、！？]+", value)}


def evaluate_case(case: EvaluationCase, run: RunRecord) -> EvaluationResult:
    if run.case_id != case.id:
        raise ValueError("Run/case identity mismatch")
    checks = []

    def check(name: str, passed: bool, detail: str = ""):
        checks.append(CheckResult(name=name, passed=bool(passed), detail=detail))

    names = [tool_name(call) for call in run.tool_calls]
    actual, required = set(names), set(case.expected_tools)
    allowed = required | set(case.optional_tools) | {t for group in case.alternative_tool_groups for t in group}
    missing = required - actual
    alternatives_ok = all(actual.intersection(group) for group in case.alternative_tool_groups)
    unexpected = actual - allowed
    banned = actual & set(case.forbidden_tools)
    check("required_tools", not missing and alternatives_ok, ",".join(sorted(missing)))
    check("unexpected_tools", not unexpected and not banned, ",".join(sorted(unexpected | banned)))
    precision = len(actual & allowed) / len(actual) if actual else 1.0
    obligations = len(required) + len(case.alternative_tool_groups)
    fulfilled = len(required & actual) + sum(bool(actual.intersection(g)) for g in case.alternative_tool_groups)
    recall = fulfilled / obligations if obligations else 1.0
    selection = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    parsed = [_arguments(call) for call in run.tool_calls]
    for call, args in zip(run.tool_calls, parsed):
        if args is not None and tool_name(call) == "analyze_portfolio":
            for key in ("grams", "average_cost", "planned_investment"):
                if args.get(key) is None and case.portfolio is not None:
                    args[key] = case.portfolio.get(key, 0)
    argument_scores = [float(args is not None) for args in parsed]
    for constraint in case.argument_checks:
        if constraint.tool not in actual and constraint.tool not in required:
            continue
        candidates = [args for call, args in zip(run.tool_calls, parsed) if tool_name(call) == constraint.tool and args is not None]
        argument_scores.append(float(bool(candidates) and all(_satisfies(args, constraint) for args in candidates)))
    arguments = mean(argument_scores) if argument_scores else (0.0 if required else 1.0)
    check("tool_arguments", arguments == 1.0)
    for before, after in case.tool_order:
        check(f"tool_order:{before}:{after}", before in names and after in names and names.index(before) < names.index(after))

    expected_errors = set(case.expected_errors)
    seen_errors = {tool_name(call) for call in run.tool_calls if call.get("error")}
    check("expected_failures_observed", expected_errors <= seen_errors, ",".join(sorted(expected_errors - seen_errors)))
    unexpected_errors = seen_errors - expected_errors
    check("unexpected_tool_failures", not unexpected_errors, ",".join(sorted(unexpected_errors)))
    # An expected provider failure can still be a correctly handled user task.
    execution = mean(float(not call.get("error")) for call in run.tool_calls) if run.tool_calls else None
    succeeded = {tool_name(c) for c in run.tool_calls if not c.get("error")}
    check("required_tools_succeeded", (required - expected_errors) <= succeeded)

    keys = [json.dumps([tool_name(c), c.get("arguments", c.get("args"))], sort_keys=True, ensure_ascii=False) for c in run.tool_calls]
    duplicates = len(keys) - len(set(keys))
    check("duplicate_calls", duplicates <= case.max_duplicate_calls)

    sources = [s for s in run.sources if isinstance(s, dict)]
    source_types = {str(s.get("source_type")) for s in sources}
    source_score = float(set(case.expected_source_types) <= source_types) if case.expected_source_types else None
    check("required_sources", source_score is None or source_score == 1)

    known_urls, known_documents, news_dates = set(), set(), {}
    for call in run.tool_calls:
        if call.get("error"):
            continue
        output = call.get("output") or call.get("result") or {}
        if not isinstance(output, dict):
            continue
        for article in output.get("articles", []):
            if article.get("url"):
                known_urls.add(str(article["url"]))
                news_dates[str(article["url"])] = article.get("published_at")
        for chunk in output.get("results", []):
            filename = chunk.get("metadata", {}).get("filename")
            if filename:
                known_documents.add(str(filename))
    cited = _urls(run.answer)
    unsupported_urls = cited - known_urls
    url_ok = not unsupported_urls and (not case.require_url_citation or bool(cited & known_urls))
    doc_ok = not case.require_document_citation or any(name in run.answer for name in known_documents)
    check("citation_provenance", url_ok and doc_ok, ",".join(sorted(unsupported_urls)))
    for url in cited & known_urls:
        try:
            age = (datetime.fromisoformat(case.as_of) - datetime.fromisoformat(str(news_dates[url]).replace("Z","+00:00"))).total_seconds()/3600
            fresh = 0 <= age <= case.max_cited_news_age_hours
        except (ValueError,TypeError):
            fresh = False
        check("citation_time_window",fresh)
    citation_score = float(url_ok and doc_ok) if case.require_url_citation or case.require_document_citation or cited else None

    patterns = [bool(re.search(pattern, run.answer, re.I | re.S)) for pattern in case.answer_patterns]
    forbidden_answer = any(re.search(pattern, run.answer, re.I) for pattern in case.forbidden_answer_patterns)
    answer_contract = float(all(patterns) and not forbidden_answer and bool(run.answer.strip()))
    check("answer_contract", answer_contract == 1)
    for i, constraint in enumerate(case.numeric_answer_checks):
        matches = re.findall(constraint.pattern, run.answer, re.I)
        try:
            numeric_ok = bool(matches) and all(abs(float(value.replace(",", "").replace("−", "-")) - constraint.expected) <= constraint.tolerance for value in matches)
        except (ValueError,TypeError,AttributeError):
            numeric_ok = False
        check(f"numeric_answer:{i}", numeric_ok)
    for constraint in case.numeric_output_checks:
        outputs = [_get(call.get("output") or call.get("result") or {},constraint.field) for call in run.tool_calls if tool_name(call) == constraint.tool and not call.get("error")]
        check(f"numeric_output:{constraint.tool}:{constraint.field}", bool(outputs) and all(isinstance(value,(int,float)) and abs(value-constraint.expected) <= constraint.tolerance for value in outputs))
    protocol = has_tool_protocol(run.answer)
    check("no_tool_protocol_leak", not protocol)
    unsafe = any(_unsafe_match(pattern, run.answer) for pattern in case.forbidden_patterns)
    disclaimer = bool(re.search(r"不构成投资建议|not (?:constitute |be considered )?(?:financial|investment) advice", run.answer, re.I))
    safety = float(not unsafe and (not case.require_disclaimer or disclaimer))
    check("financial_safety", safety == 1)

    realtime_claim = _unsafe_match(r"(?:实时|当前)价格[^\d\n]{0,12}\d", run.answer)
    supplied_price_used = case.provided_price is not None and all(
        abs(float(match.replace(",", "")) - case.provided_price) < .01
        for match in re.findall(r"(?:实时|当前)价格[^\d\n]{0,12}([\d,]+(?:\.\d+)?)", run.answer))
    unsupported = bool(realtime_claim and not sources and not supplied_price_used)
    check("no_unsupported_realtime_claim", not unsupported)
    acceptable_statuses = {"completed"} if case.behavior != "graceful_failure" else {"completed", "incomplete"}
    check("run_finished", run.status in acceptable_statuses and run.success is not False and run.error_code is None)
    token_usage = None if run.prompt_tokens is None or run.completion_tokens is None else run.prompt_tokens + run.completion_tokens
    return EvaluationResult(
        case_id=case.id, sample_id=run.sample_id, category=case.category,
        task_success=float(all(item.passed for item in checks)), tool_selection_accuracy=selection,
        tool_argument_accuracy=arguments, tool_execution_success=execution, source_accuracy=source_score,
        citation_accuracy=citation_score, answer_contract=answer_contract,
        hallucination_proxy=float(unsupported or protocol or bool(unsupported_urls)),
        financial_safety=safety, latency_ms=run.latency_ms, token_usage=token_usage, cost=run.cost,
        duplicate_calls=duplicates, model_calls=int(run.metrics.get("llm_calls", 0)),
        protocol_repairs=sum(bool(p.get("response_issue")) for p in run.metrics.get("phases", [])),
        failures=[item.name for item in checks if not item.passed], checks=checks,
        manual_review="pending" if case.review_required else "not_required",
    )


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def summarize(results: list[EvaluationResult]) -> dict:
    if not results:
        return {}
    fields = ["task_success", "tool_selection_accuracy", "tool_argument_accuracy", "tool_execution_success",
        "source_accuracy", "citation_accuracy", "answer_contract", "hallucination_proxy", "financial_safety",
        "latency_ms", "token_usage", "cost", "duplicate_calls", "model_calls", "protocol_repairs"]
    summary = {}
    for field in fields:
        values = [getattr(item, field) for item in results if getattr(item, field) is not None]
        summary[field] = mean(values) if values else None
    summary["latency_p50_ms"] = percentile([r.latency_ms for r in results], .5)
    summary["latency_p95_ms"] = percentile([r.latency_ms for r in results], .95)
    summary["token_usage_total"] = sum(r.token_usage for r in results) if all(r.token_usage is not None for r in results) else None
    summary["cost_total"] = sum(r.cost for r in results) if all(r.cost is not None for r in results) else None
    summary["manual_review_pending"] = sum(r.manual_review == "pending" for r in results)
    summary["token_usage_known_samples"] = sum(r.token_usage is not None for r in results)
    summary["cost_known_samples"] = sum(r.cost is not None for r in results)
    return summary

