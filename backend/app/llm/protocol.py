"""Detect textual tool envelopes; never interpret them as executable calls."""
import html
import re

TOOL_PROTOCOL = re.compile(r"<\s*(?:/?tool_call\b|function\s*=|parameter\s*=)", re.I)
PROTOCOL_NOTICE = "这条回答包含未执行的工具指令，不能作为已完成分析。请重新发送问题。"


def has_tool_protocol(content: str) -> bool:
    return bool(TOOL_PROTOCOL.search(html.unescape(content)))


def strip_tool_protocol(content: str) -> str:
    """Display-only cleanup of legacy answers, including truncated envelopes."""
    decoded = html.unescape(content)
    if not TOOL_PROTOCOL.search(decoded):
        return content
    decoded = re.sub(r"```[^\n]*\n.*?```", lambda match: "" if TOOL_PROTOCOL.search(match.group()) else match.group(), decoded, flags=re.S)
    decoded = re.sub(r"<\s*tool_call\b[^>]*>.*?<\s*/tool_call\s*>", "", decoded, flags=re.I | re.S)
    decoded = re.sub(r"<\s*(?:/?tool_call\b|function\s*=|parameter\s*=).*", "", decoded, flags=re.I | re.S)
    return decoded.strip()
