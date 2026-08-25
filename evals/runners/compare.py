"""Compare two evaluation reports and fail on configured regressions."""

import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser();parser.add_argument("baseline",type=Path);parser.add_argument("candidate",type=Path);parser.add_argument("--tolerance",type=float,default=0.02);args=parser.parse_args()
    baseline=json.loads(args.baseline.read_text(encoding="utf-8"))["summary"];candidate=json.loads(args.candidate.read_text(encoding="utf-8"))["summary"]
    higher_better={"task_success","tool_selection_accuracy","tool_argument_accuracy","tool_execution_success","source_accuracy","financial_safety"}
    regressions=[]
    for metric in higher_better:
        if metric in baseline and candidate.get(metric,0) < baseline[metric]-args.tolerance: regressions.append(metric)
    print(json.dumps({"regressions":regressions,"baseline":baseline,"candidate":candidate},ensure_ascii=False,indent=2))
    raise SystemExit(1 if regressions else 0)
if __name__=="__main__":main()
