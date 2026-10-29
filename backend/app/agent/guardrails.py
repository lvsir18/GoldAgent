"""Deterministic financial verification and answer guardrails."""

from __future__ import annotations

import re
from typing import Any
from ..core.presentation import tool_name, public_answer
from ..llm.protocol import has_tool_protocol


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
                issues.append(f"{tool_name(result.get('tool'))}使用了较早数据，请核查最新变化")
            if metadata.get("source_type") == "derived":
                issues.append(f"{tool_name(result.get('tool'))}为换算参考行情，不是直接交易报价")
        if result.get("error"):
            issues.append(f"{tool_name(result.get('tool'))}暂时获取失败，相关结论可能不完整，请稍后重试")
    return {"passed": not any(result.get("error") for result in tool_results), "issues": list(dict.fromkeys(issues)), "sources": sources}


def apply_financial_guardrail(answer: str, verification: dict[str, Any] | None, has_portfolio: bool) -> tuple[str, list[str]]:
    flags: list[str] = ["invalid_tool_protocol"] if has_tool_protocol(answer) else []
    cleaned = public_answer(answer).strip()
    for pattern in PROHIBITED_CERTAINTY:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(pattern, "存在不确定性", cleaned, flags=re.IGNORECASE)
            flags.append("removed_guaranteed-return language")
    position_advice = re.sub(r"(?:不建议|不要|避免|切勿|不应|禁止)\s*(?:使用|投入|配置|买入)?\s*(?:满仓|全部资金|精确仓位|仓位\s*100%)", "", cleaned)
    if not has_portfolio and re.search(r"(?:满仓|全部资金|精确仓位|仓位\s*100%)", position_advice):
        cleaned += "\n\n由于缺少完整持仓和风险信息，以上仓位描述不能作为精确执行指令。"
        flags.append("missing portfolio context")
    issues = (verification or {}).get("issues", [])
    if issues:
        cleaned += "\n\n数据说明：" + "；".join(issues)
    disclaimer = "仅供投资分析参考，不构成投资建议，也不执行任何自动交易。"
    if disclaimer not in cleaned:
        cleaned += f"\n\n{disclaimer}"
    return cleaned, flags

