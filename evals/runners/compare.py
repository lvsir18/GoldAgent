"""Compare two evaluation reports and fail on configured regressions."""

import argparse
import json
from pathlib import Path


def compare_reports(baseline, candidate, tolerance=.02):
    if baseline.get("schema_version") != 2 or candidate.get("schema_version") != 2:
        raise ValueError("Only version-2 reports are comparable")
    for report in (baseline,candidate):
        if not report["coverage"]["complete"]:
            raise ValueError("Incomplete benchmark coverage")
    for field in ("dataset_sha256","fixture_version","fixture_sha256","evaluator_sha256","repeats","engine"):
        if baseline["manifest"].get(field) != candidate["manifest"].get(field):
            raise ValueError(f"Incompatible benchmark {field}")
    first = {(c["case_id"],c["sample_id"]) for c in baseline["cases"]}
    second = {(c["case_id"],c["sample_id"]) for c in candidate["cases"]}
    if first != second:
        raise ValueError("Compared samples differ")
    higher = {"task_success","tool_selection_accuracy","tool_argument_accuracy","source_accuracy","citation_accuracy","answer_contract","financial_safety"}
    lower = {"hallucination_proxy","duplicate_calls"}
    regressions = []
    for name in higher | lower:
        old, new = baseline["summary"].get(name), candidate["summary"].get(name)
        if old is not None and (new is None or (new < old - tolerance if name in higher else new > old + tolerance)):
            regressions.append(name)
    changed = {key:{"baseline":baseline["manifest"].get(key),"candidate":candidate["manifest"].get(key)}
        for key in ("model","provider","research_mode","agent_config","concurrency") if baseline["manifest"].get(key) != candidate["manifest"].get(key)}
    return {"regressions":sorted(regressions),"configuration_changes":changed,
        "baseline":baseline["summary"],"candidate":candidate["summary"],
        "paired_cases":[{"case_id":cid,"sample_id":sample,
            "baseline_failures":next(c["failures"] for c in baseline["cases"] if (c["case_id"],c["sample_id"]) == (cid,sample)),
            "candidate_failures":next(c["failures"] for c in candidate["cases"] if (c["case_id"],c["sample_id"]) == (cid,sample))} for cid,sample in sorted(first)]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("baseline",type=Path);parser.add_argument("candidate",type=Path);parser.add_argument("--tolerance",type=float,default=0.02);args=parser.parse_args()
    if args.tolerance < 0:
        parser.error("Tolerance must not be negative")
    result = compare_reports(json.loads(args.baseline.read_text(encoding="utf-8")),json.loads(args.candidate.read_text(encoding="utf-8")),args.tolerance)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(1 if result["regressions"] else 0)
if __name__=="__main__":main()
