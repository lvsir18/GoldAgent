"""Report persistence-facing service."""

from datetime import datetime, timezone
from typing import Any


class ReportService:
    def render_markdown(self, report_type: str, title: str, payload: dict[str, Any]) -> str:
        lines = [f"# {title}", "", f"- 类型：{report_type}", f"- 生成时间：{datetime.now(timezone.utc).isoformat()}", "", "## 数据", ""]
        for key, value in payload.items():
            lines.append(f"- **{key}**：{value}")
        lines.extend(["", "---", "仅供投资分析参考，不构成投资建议。"])
        return "\n".join(lines)

