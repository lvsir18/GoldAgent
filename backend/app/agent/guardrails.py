"""Deterministic financial verification and answer guardrails."""

from __future__ import annotations

import re
from typing import Any


PROHIBITED_CERTAINTY = (
    r"保证上涨", r"保证下跌", r"稳赚", r"必赚", r"100%\s*(?:上涨|盈利|准确)", r"绝对不会亏",
)


def verify_tool_results(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    sources: list[dict[str, Any]] = []
    for result in tool_results:
        payload = result.get("output") or {}
        metadata = payload.get("metadata") if isinstance(payload, dict) else None
        if metadata:
            sources.append(metadata)
            if metadata.get("is_stale"):
                issues.append(f"{result.get('tool')} returned stale data")
            if metadata.get("source_type") == "derived":
                issues.append(f"{result.get('tool')} returned derived, not direct, market data")
        if result.get("error"):
            issues.append(f"{result.get('tool')} failed: {result['error']}")
    return {"passed": not any("failed" in issue for issue in issues), "issues": issues, "sources": sources}


def apply_financial_guardrail(answer: str, verification: dict[str, Any] | None, has_portfolio: bool) -> tuple[str, list[str]]:
    cleaned = answer.strip()
    flags: list[str] = []
    for pattern in PROHIBITED_CERTAINTY:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(pattern, "存在不确定性", cleaned, flags=re.IGNORECASE)
            flags.append("removed_guaranteed-return language")
    if not has_portfolio and re.search(r"(?:满仓|全部资金|精确仓位|仓位\s*100%)", cleaned):
        cleaned += "\n\n由于缺少完整持仓和风险信息，以上仓位描述不能作为精确执行指令。"
        flags.append("missing portfolio context")
    issues = (verification or {}).get("issues", [])
    if issues:
        cleaned += "\n\n数据说明：" + "；".join(issues)
    disclaimer = "仅供投资分析参考，不构成投资建议，也不执行任何自动交易。"
    if disclaimer not in cleaned:
        cleaned += f"\n\n{disclaimer}"
    return cleaned, flags

