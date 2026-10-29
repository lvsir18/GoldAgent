"""Execute the real Agent against frozen tools; live LLM requires explicit opt-in."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit

from backend.app.agent.graph import GoldAgentRuntime
from backend.app.llm.gateway import build_llm_gateway
from src.settings import AppSettings
from evals.models import RunRecord
from evals.fixtures import fixture_tools
from evals.replay import ReplayGateway
from evals.budget import Budget, BudgetExceeded, MeteredGateway
from evals.reporting import load_cases, build_report, write_report, source_fingerprint

ROOT = Path(__file__).resolve().parents[2]


def configured_settings(engine, research_mode):
    settings = AppSettings.load(ROOT / "config.yaml") if engine == "model" else AppSettings()
    update = {"research_mode":research_mode}
    if research_mode == "quick":
        update.update(max_steps=min(settings.agent.max_steps, 4), max_tokens=min(settings.agent.max_tokens,1600),
            run_timeout_seconds=min(settings.agent.run_timeout_seconds,90))
    return settings.model_copy(update={"agent":settings.agent.model_copy(update=update)})


async def execute_case(case, sample, settings, engine, budget):
    ledger = {"calls":0,"prompt_tokens":0,"completion_tokens":0,"usage_complete":True}
    gateway = (MeteredGateway(build_llm_gateway(settings), budget, ledger) if engine == "model" else ReplayGateway(case))
    runtime = GoldAgentRuntime(settings, gateway, fixture_tools(case,settings))
    started, error_code, state = time.perf_counter(), None, {}
    try:
        state = await runtime.invoke(user_message=case.query, user_id="synthetic-evaluation-user",
            session_id=f"{case.id}-{sample}", portfolio_context=case.portfolio, risk_profile=case.risk_profile,
            user_preferences={"response_language":case.language,"response_style":"concise","show_sources":True,
                "custom_instructions":f"本次使用固定合成评测资料，参考时点为 {case.as_of}，不是实际市场行情。请注明资料局限，以简短结论回答；引用所用资料。"},
            history=case.history)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error_code = "budget_exhausted" if isinstance(exc,BudgetExceeded) else "provider_error" if engine == "model" else "replay_error"
        # Do not write exception strings: upstream errors can contain private URLs.
        snapshot = await runtime.graph.aget_state({"configurable":{"thread_id":f"synthetic-evaluation-user:{case.id}-{sample}"}})
        state = snapshot.values or {}
    tools = state.get("tool_results", [])
    sources = [c["output"]["metadata"] for c in tools if not c.get("error") and isinstance(c.get("output"),dict) and isinstance(c["output"].get("metadata"),dict)]
    usage = state.get("usage", {})
    known_usage = engine != "model" or ledger["usage_complete"]
    return RunRecord(case_id=case.id,sample_id=sample,answer=state.get("final_answer") or "研究未完成。",
        tool_calls=tools,sources=sources,status=error_code or state.get("status", "failed"),error_code=error_code,
        latency_ms=round((time.perf_counter()-started)*1000,2),
        prompt_tokens=ledger["prompt_tokens"] if engine == "model" and known_usage else None,
        completion_tokens=ledger["completion_tokens"] if engine == "model" and known_usage else None,
        cost=0 if engine == "replay" else None,
        metrics={"llm_calls":ledger["calls"] if engine == "model" else state.get("current_step",0),
            "phases":state.get("performance",[]),"usage":usage,
            "guardrail_flags":(state.get("verification_result") or {}).get("guardrail_flags",[])})


async def run_benchmark(cases, settings, engine, budget, repeats, concurrency, output):
    records = []
    semaphore = asyncio.Semaphore(concurrency)
    try:
        revision = subprocess.check_output(["git","-c",f"safe.directory={ROOT.as_posix()}","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git","-c",f"safe.directory={ROOT.as_posix()}","status","--porcelain"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip())
    except (OSError,subprocess.CalledProcessError):
        revision = "unknown"
        dirty = None
    metadata = {"engine":engine,"model":settings.agent.model if engine == "model" else "oracle-script",
        "provider":settings.agent.provider if engine == "model" else "offline",
        "research_mode":settings.agent.research_mode,"git_revision":revision,
        "working_tree_dirty":dirty,
        "runtime_sha256":source_fingerprint(sorted(path.relative_to(ROOT).as_posix()
            for folder in ("backend/app/agent","backend/app/tools","backend/app/services","backend/app/llm")
            for path in (ROOT / folder).rglob("*.py")) + ["src/settings.py","config.yaml"]),
        "measures_model_quality":engine == "model", "data_policy":"synthetic-only; no application DB or external market/news calls",
        "agent_config":settings.agent.model_dump(mode="json",exclude={"api_url"}),"concurrency":concurrency}

    def save():
        output.mkdir(parents=True,exist_ok=True)
        (output / "cases.jsonl").write_text("\n".join(c.model_dump_json() for c in cases)+"\n",encoding="utf-8")
        (output / "runs.jsonl").write_text("\n".join(r.model_dump_json() for r in records) + "\n",encoding="utf-8")
        report = build_report(cases,records,repeats=repeats,metadata={**metadata,"budget":budget.snapshot()})
        write_report(report,output / "report.json")
        questions = {case.id:case.query for case in cases}
        reviews = [{"case_id":r.case_id,"sample_id":r.sample_id,"question":questions[r.case_id],"answer":r.answer,
            "review":{"usefulness":None,"citation_entailment":None,"missing_evidence":None,"notes":""}}
            for r in records if next(case for case in cases if case.id == r.case_id).review_required]
        (output / "review.jsonl").write_text("\n".join(json.dumps(item,ensure_ascii=False) for item in reviews)+"\n",encoding="utf-8")
        return report

    async def run_one(case,sample):
        async with semaphore:
            record = await execute_case(case,sample,settings,engine,budget)
            records.append(record)
            report = save()  # Persist each completed sample, not only at batch end.
            result = next(r for r in report["cases"] if r["case_id"] == case.id and r["sample_id"] == sample)
            print(json.dumps({"case":case.id,"sample":sample,"status":record.status,"passed":bool(result["task_success"]),"failures":result["failures"]},ensure_ascii=False),flush=True)

    try:
        async with asyncio.timeout(budget.wall_seconds):
            await asyncio.gather(*(run_one(case,sample) for case in cases for sample in range(1,repeats+1)))
    except TimeoutError:
        metadata["interrupted"] = "wall_budget"
    finally:
        report = save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",type=Path,default=ROOT / "evals/datasets/goldagent_cases.jsonl")
    parser.add_argument("--engine",choices=["replay","model"],default="replay")
    parser.add_argument("--suite",choices=["full","smoke"],default="full")
    parser.add_argument("--case-ids",help="Comma-separated explicit subset; recorded in manifest")
    parser.add_argument("--research-mode",choices=["quick","deep"],default="quick")
    parser.add_argument("--repeats",type=int,default=1)
    parser.add_argument("--concurrency",type=int,choices=[1,2],default=1)
    parser.add_argument("--allow-paid",action="store_true")
    parser.add_argument("--provider-host",default="api.xiaomimimo.com",help="Explicit approved live LLM host")
    parser.add_argument("--max-model-calls",type=int,default=64)
    parser.add_argument("--max-output-tokens",type=int,default=65536)
    parser.add_argument("--max-input-chars",type=int,default=750000)
    parser.add_argument("--wall-seconds",type=int,default=900)
    parser.add_argument("--output-dir",type=Path)
    args = parser.parse_args()
    if args.engine == "model" and not args.allow_paid:
        parser.error("Live model evaluation requires --allow-paid; default replay makes no paid calls")
    if min(args.repeats,args.max_model_calls,args.max_output_tokens,args.max_input_chars,args.wall_seconds) < 1:
        parser.error("Budgets and repeats must be positive")
    settings = configured_settings(args.engine,args.research_mode)
    if args.engine == "model":
        url = urlsplit(str(settings.agent.api_url))
        if url.scheme != "https" or url.hostname != args.provider_host or url.username or url.password or url.query:
            parser.error("Live provider URL does not match explicitly approved HTTPS host")
    cases = load_cases(args.dataset,args.suite,args.case_ids.split(",") if args.case_ids else None)
    output = args.output_dir or ROOT / "data/evals" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = asyncio.run(run_benchmark(cases,settings,args.engine,
        Budget(args.max_model_calls,args.max_output_tokens,args.max_input_chars,args.wall_seconds),args.repeats,args.concurrency,output))
    print(json.dumps({"coverage":report["coverage"],"summary":report["summary"],"output":str(output)},ensure_ascii=False,indent=2))
    raise SystemExit(0 if report["coverage"]["complete"] and report["summary"].get("task_success") == 1 else 1)


if __name__ == "__main__":
    main()
