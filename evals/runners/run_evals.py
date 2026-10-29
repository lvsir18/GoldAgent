"""Evaluate recorded Agent runs without making paid API calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.models import RunRecord
from evals.reporting import load_jsonl, load_cases, build_report, write_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=Path("evals/datasets/goldagent_cases.jsonl"))
    parser.add_argument("--runs", type=Path, required=True, help="Recorded Agent run JSONL")
    parser.add_argument("--output", type=Path, default=Path("data/evals/rescored/report.json"))
    parser.add_argument("--suite", choices=["full", "smoke"], default="full")
    parser.add_argument("--case-ids", help="Explicit comma-separated subset")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--manifest", type=Path, help="Original report: verifies dataset, mode and repeat provenance")
    parser.add_argument("--allow-contract-update", action="store_true", help="Explicitly rescore an unchanged recording with revised contracts; record both hashes")
    args = parser.parse_args()
    cases = load_cases(args.dataset,args.suite,args.case_ids.split(",") if args.case_ids else None)
    runs = load_jsonl(args.runs, RunRecord)
    metadata = {"engine":"recorded", "measures_model_quality":False}
    if args.manifest:
        original = json.loads(args.manifest.read_text(encoding="utf-8"))
        metadata = original["manifest"]
        if metadata["repeats"] != args.repeats or set(metadata["case_ids"]) != {c.id for c in cases}:
            raise ValueError("Original manifest does not match selected cases/repeats")
    report = build_report(cases,runs,repeats=args.repeats,metadata=metadata)
    if args.manifest:
        for field in ("execution_sha256","fixture_sha256"):
            if original["manifest"].get(field) and report["manifest"][field] != original["manifest"][field]:
                raise ValueError(f"Execution inputs changed ({field}); rerun Agent instead of rescoring")
        report["manifest"]["execution_inputs_verified"] = bool(original["manifest"].get("execution_sha256"))
    if args.manifest and report["manifest"]["dataset_sha256"] != original["manifest"]["dataset_sha256"]:
        if not args.allow_contract_update:
            raise ValueError("Dataset changed since original execution; explicit --allow-contract-update required")
        report["manifest"]["rescored_from_dataset_sha256"] = original["manifest"]["dataset_sha256"]
        report["manifest"]["contract_update"] = True
    if args.manifest:
        report["manifest"]["original_evaluator_sha256"] = original["manifest"].get("evaluator_sha256")
        report["manifest"]["original_report"] = str(args.manifest)
        report["manifest"]["executed_at"] = original["manifest"].get("executed_at",original["manifest"].get("created_at"))
    write_report(report,args.output)
    print(json.dumps({"coverage":report["coverage"],"summary":report["summary"]},ensure_ascii=False,indent=2))
    raise SystemExit(0 if report["coverage"]["complete"] and report["summary"].get("task_success") == 1 else 1)


if __name__ == "__main__": main()
