"""Loss-aware LLM context views; full tool evidence remains in run storage."""
from copy import deepcopy
import json
from typing import Any


def _sample(values: list, limit: int) -> list:
    if len(values) <= limit:
        return values
    return [values[round(i * (len(values) - 1) / (limit - 1))] for i in range(limit)]


def tool_context(tool: str, output: Any) -> str:
    if not isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, default=str)
    view = deepcopy(output)
    omitted = {}
    if tool == "get_market_history" and len(view.get("points", [])) > 96:
        omitted["points"] = {"original_count": len(view["points"]), "shown": 96, "method": "evenly sampled, not a continuous price series; do not recompute indicators on these samples"}
        view["points"] = _sample(view["points"], 96)
    if tool == "run_backtest":
        for key in ("equity_curve", "drawdown_curve", "benchmark_curve"):
            if len(view.get(key, [])) > 12:
                omitted[key] = {"original_count": len(view[key]), "shown": 12, "method": "sampled; metrics are computed on the full original ledger"}
                view[key] = _sample(view[key], 12)
        if len(view.get("trades", [])) > 16:
            omitted["trades"] = {"original_count": len(view["trades"]), "shown": 16, "method": "latest trades only"}
            view["trades"] = view["trades"][-16:]
    if tool == "search_financial_news":
        for article in view.get("articles", []):
            summary = article.get("summary") or ""
            if len(summary) > 280:
                article["summary"] = summary[:280]
                article["summary_truncated"] = True
    if omitted:
        view["context_limits"] = omitted
        view["full_evidence"] = "Full original output is retained in this research run. Missing detail is not evidence of absence."
    return json.dumps(view, ensure_ascii=False, default=str, separators=(",", ":"))


def bounded_history(history: list[dict[str, str]], max_chars: int = 24000) -> list[dict[str, str]]:
    selected, size = [], 0
    for item in reversed(history[-30:]):
        if item.get("role") not in {"user", "assistant"}:
            continue
        content = item["content"]
        if size + len(content) > max_chars:
            if not selected:
                selected.append({**item, "content": content[-max_chars:] + "\n[Earlier content omitted by the context budget]"})
            break
        selected.append(item); size += len(content)
    return list(reversed(selected))
