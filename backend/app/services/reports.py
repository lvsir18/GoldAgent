"""Report persistence-facing service."""

from datetime import datetime, timezone
from typing import Any
import json


class ReportService:
    def render_markdown(self, report_type: str, title: str, payload: dict[str, Any]) -> str:
        lines = [f"# {title}", "", f"- 类型：{report_type}", f"- 生成时间：{datetime.now(timezone.utc).isoformat()}", "", "## 数据", ""]
        if payload.get("final_answer"):
            lines.extend(["## 研究问题", str(payload.get("question", "")), "", "## 研究结论", payload["final_answer"], ""])
        for key, value in payload.items():
            if key == "final_answer":
                continue
            if isinstance(value, (dict, list)):
                lines.extend([f"### {key}", "", "```json", json.dumps(value, ensure_ascii=False, indent=2, default=str), "```", ""])
            else:
                lines.append(f"- **{key}**：{value}")
        lines.extend(["", "---", "仅供投资分析参考，不构成投资建议。"])
        return "\n".join(lines)

