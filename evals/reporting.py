"""Auditable manifests, complete coverage checks, category scores and review queue."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from evals.evaluators.core import evaluate_case, summarize
from evals.models import EvaluationCase, RunRecord
from evals.fixtures import FIXTURE_VERSION

REPORT_VERSION = 2
SMOKE_IDS = ["market-01", "market-02", "technical-01", "news-02", "forecast-02",
    "portfolio-01", "backtest-01", "rag-04", "multi-01", "safety-03", "general-01",
    "failure-02", "saved-portfolio-latest", "no-portfolio-clarify", "protocol-text-regression", "injection-doc"]


def load_jsonl(path: Path, schema):
    return [schema.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_cases(path: Path, suite="full", case_ids=None):
    all_cases = load_jsonl(path, EvaluationCase)
    ids = [case.id for case in all_cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate dataset case IDs")
    selected = set(case_ids or (SMOKE_IDS if suite == "smoke" else ids))
    if not selected or selected - set(ids):
        raise ValueError("Empty selection or unknown case IDs")
    return [case for case in all_cases if case.id in selected]


def fingerprint(cases):
    content = json.dumps([c.model_dump(mode="json") for c in cases], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def execution_fingerprint(cases):
    # Scoring changes may be rescored; changed model inputs must be re-executed.
    fields = {"id","query","portfolio","risk_profile","history","as_of","language","scenario"}
    content = json.dumps([c.model_dump(mode="json",include=fields) for c in cases],sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()


def source_fingerprint(paths):
    digest = hashlib.sha256()
    root = Path(__file__).resolve().parents[1]
    for name in paths:
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def build_report(cases, runs, *, repeats=1, metadata=None):
    if repeats < 1:
        raise ValueError("Repeats must be positive")
    by_id = {case.id:case for case in cases}
    expected = {(case.id, sample) for case in cases for sample in range(1, repeats + 1)}
    keys = [(run.case_id, run.sample_id) for run in runs]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate case/sample recordings")
    if set(keys) - expected:
        raise ValueError("Recording contains unknown or out-of-range samples")
    missing = sorted(expected - set(keys))
    results = [evaluate_case(by_id[run.case_id], run) for run in runs]
    groups = defaultdict(list)
    for result in results:
        groups[result.category].append(result)
    failures = Counter(failure for result in results for failure in result.failures)
    categories = {}
    for category in sorted({case.category for case in cases}):
        planned = sum(case.category == category for case in cases) * repeats
        values = groups[category]
        categories[category] = {"planned":planned, "executed":len(values), "passed":sum(r.task_success == 1 for r in values), "metrics":summarize(values)}
    return {
        "schema_version":REPORT_VERSION,
        "manifest":{**(metadata or {}),"created_at":datetime.now(timezone.utc).isoformat(), "dataset_sha256":fingerprint(cases),
            "execution_sha256":execution_fingerprint(cases),
            "fixture_sha256":source_fingerprint(["evals/fixtures.py"]),
            "evaluator_sha256":source_fingerprint(["evals/models.py","evals/evaluators/core.py","evals/reporting.py"]),
            "fixture_version":FIXTURE_VERSION,"case_ids":[case.id for case in cases],"repeats":repeats},
        "coverage":{"planned":len(expected),"executed":len(runs),"complete":not missing and not any(run.status == "budget_exhausted" for run in runs),"missing":[{"case_id":cid,"sample_id":sample} for cid,sample in missing]},
        "summary":summarize(results),"categories":categories,"failure_counts":dict(failures.most_common()),
        "cases":[result.model_dump(mode="json") for result in results],
        "limitations":["task_success means deterministic contract acceptance, not expert-rated usefulness or investment performance.",
            "Citation checks validate provenance, not semantic entailment. Hallucination and safety checks are limited rule proxies.",
            "Synthetic fixtures do not measure external market/news availability or production embedding quality.",
            "Replay is oracle-driven workflow verification, not model evaluation. Cost remains null unless supplied; no guessed pricing.",
            "Missing cases invalidate the benchmark. Pending manual reviews are not treated as expert approval."],
    }


def _fmt(value, percent=False):
    if value is None:
        return "未提供 / N/A"
    return f"{value * 100:.1f}%" if percent else f"{value:.1f}"


def render_markdown(report):
    manifest, coverage, summary = report["manifest"], report["coverage"], report["summary"]
    lines = ["# GoldAgent Agent 评测报告", "", f"- 引擎：{manifest.get('engine', 'recorded')}",
        f"- 模型：{manifest.get('model', '未记录')}", f"- 研究模式：{manifest.get('research_mode', '未记录')}",
        f"- Fixture：{manifest['fixture_version']}", f"- 数据集 SHA256：`{manifest['dataset_sha256']}`",
        f"- 执行覆盖：{coverage['executed']}/{coverage['planned']}；完整：{coverage['complete']}", "",
        "> 规则验收通过不等于完整答案质量、投资准确率或收益率。Replay 不能代表真实模型能力。", "",
        "## 核心指标", "", "| 指标 | 结果 |", "|---|---|"]
    for key, label in {"task_success":"规则验收通过率", "tool_selection_accuracy":"工具集合合规 F1", "tool_argument_accuracy":"参数合规率",
        "source_accuracy":"来源类型要求满足率", "citation_accuracy":"引用来源合规率", "answer_contract":"答案规则满足率",
        "financial_safety":"金融安全规则通过率", "hallucination_proxy":"不支持声明/协议泄漏代理率（越低越好）"}.items():
        lines.append(f"| {label} | {_fmt(summary.get(key), True)} |")
    for key, label in {"latency_p50_ms":"P50 耗时（ms）", "latency_p95_ms":"P95 耗时（ms）", "token_usage_total":"已知 Token 总量", "cost_total":"已知费用总量", "manual_review_pending":"待人工审核样本数"}.items():
        lines.append(f"| {label} | {_fmt(summary.get(key))} |")
    lines += ["", "## 分类结果", "", "| 分类 | 已执行/计划 | 通过 |", "|---|---|---|"]
    for category, item in report["categories"].items():
        lines.append(f"| {category} | {item['executed']}/{item['planned']} | {item['passed']} |")
    lines += ["", "## 失败定位", ""]
    for item in report["cases"]:
        if item["failures"]:
            lines.append(f"- {item['case_id']} / {item['sample_id']}：{', '.join(item['failures'])}")
    if not report["failure_counts"]:
        lines.append("本次已执行样本未违反配置的确定性规则；仍需人工审核开放式结论。")
    lines += ["", "## 评测边界", "", *[f"- {text}" for text in report["limitations"]], ""]
    return "\n".join(lines)


def write_report(report, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
