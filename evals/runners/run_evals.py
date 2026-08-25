"""Evaluate recorded Agent runs without making paid API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.evaluators.core import EvaluationCase, RunRecord, evaluate_case, summarize


def load_jsonl(path: Path, schema):
    return [schema.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/goldagent_cases.jsonl"))
    parser.add_argument("--runs", type=Path, required=True, help="Recorded Agent run JSONL")
    parser.add_argument("--output", type=Path, default=Path("evals/reports/latest.json"))
    args = parser.parse_args()
    cases = {case.id: case for case in load_jsonl(args.dataset, EvaluationCase)}
    runs = load_jsonl(args.runs, RunRecord)
    results = [evaluate_case(cases[run.case_id], run) for run in runs if run.case_id in cases]
    payload = {"summary": summarize(results), "cases": [item.model_dump() for item in results]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
