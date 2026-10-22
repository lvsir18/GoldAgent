"""Report persistence-facing service."""

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from ..core.presentation import limitation_text, public_answer, source_name, tool_name
from .research import research_evidence


class ReportService:
    def render_markdown(self, report_type: str, title: str, payload: dict[str, Any], created_at: datetime | None = None) -> str:
        """Allowlist facts for readers; never serialize run state or tool arguments."""
        generated = (created_at or datetime.now(timezone.utc)).isoformat()
        lines = [f"# {title}", "", f"- 生成时间：{generated}", ""]
        if payload.get("question"):
            lines.extend(["## 研究问题", "", str(payload["question"]), ""])
        if payload.get("final_answer"):
            lines.extend(["## 研究结论", "", public_answer(str(payload["final_answer"])), ""])
        snapshot = payload.get("market_snapshot") or ({"price": payload["price"]} if isinstance(payload.get("price"), (int, float)) else {})
        if isinstance(snapshot, dict) and snapshot:
            lines.extend(["## 行情快照", "", "以下为保存时的行情记录，并非持续更新的实时报价。", ""])
            metadata = snapshot.get("metadata") or {}
            currency = str(metadata.get("currency", "")).split("/")[0]
            unit = "元/克" if currency == "CNY" else "美元/盎司" if currency == "USD" else "以原始来源计价单位为准"
            for key, label in {"price": f"参考价格（{unit}）", "change_1d_pct": "日涨跌幅（%）", "change_1w_pct": "周涨跌幅（%）", "change_1m_pct": "月涨跌幅（%）"}.items():
                value = snapshot.get(key)
                if isinstance(value, (int, float)):
                    lines.append(f"- {label}：{value}")
            lines.append(f"- 来源：{source_name(metadata.get('source'))}")
            for key, label in {"price_timestamp": "价格时间", "retrieved_at": "获取时间", "data_end": "数据截至"}.items():
                if metadata.get(key):
                    lines.append(f"- {label}：{metadata[key]}")
        results = payload.get("tool_results") or []
        evidence = payload.get("evidence") or (research_evidence(results) if not snapshot else {})
        citations = evidence.get("citations") or []
        if citations:
            lines.extend(["", "## 引用来源", ""])
            for citation in citations:
                url = citation.get("url") or ""
                label = str(citation.get("title") or "参考资料").replace("\n", " ")
                if urlparse(url).scheme in {"http", "https"}:
                    lines.append(f"- [{label}]({url}) · {source_name(citation.get('source'))} · 发布时间：{citation.get('published_at') or '待确认'}")
                else:
                    lines.append(f"- {label} · 页码：{citation.get('page') or '—'}")
        snapshots = evidence.get("snapshots") or []
        if snapshots:
            lines.extend(["", "## 行情来源与时间", ""])
            for item in snapshots:
                metadata = item.get("metadata") or {}
                lines.append(f"- {tool_name(item.get('tool'))} · {source_name(metadata.get('source'))} · 获取时间：{metadata.get('retrieved_at') or '待确认'}")
        limitations = list(evidence.get("limitations") or [])
        if snapshot:
            if snapshot.get("metadata", {}).get("is_stale"):
                limitations.append("较早数据")
            if snapshot.get("metadata", {}).get("is_derived"):
                limitations.append("换算参考行情")
        if limitations:
            lines.extend(["", "## 研究边界", ""])
            # Rebuild from facts so old raw exceptions cannot leak through downloads.
            safe = [limitation_text(value) for value in limitations]
            lines.extend(f"- {item}" for item in dict.fromkeys(safe))
        if not payload.get("final_answer") and not snapshot:
            lines.append("暂无可展示的研究结论或行情快照。")
        lines.extend(["", "---", "仅供投资分析参考，不构成投资建议。"])
        return "\n".join(lines)

