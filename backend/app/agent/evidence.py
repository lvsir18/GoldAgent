"""Bounded links from actual tool evidence, never guessed source citations."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, unquote
from ..core.citations import cited_urls


def _url(value):
    if not isinstance(value, str) or re.search(r"[\s<>\\]", value):
        return None
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        return value
    except ValueError:
        return None


def _label(value, limit=120):
    return re.sub(r"[\[\]<>`*|\\\r\n]", " ", str(value or "")).strip()[:limit]


def append_news_evidence(answer: str, tool_results: list[dict], language="auto") -> tuple[str, list[str]]:
    references, seen = [], set()
    for result in tool_results:
        if result.get("tool", result.get("name")) != "search_financial_news" or result.get("error"):
            continue
        output = result.get("output")
        if not isinstance(output, dict):
            continue
        for article in output.get("articles", []):
            if not isinstance(article, dict):
                continue
            url = _url(article.get("url"))
            if not url or url in seen:
                continue
            seen.add(url)
            references.append((url, article))
    # If the answer already contains actual cited links, preserve its own source
    # selection; avoid appending unrelated retrieved results to a cited answer.
    cited = cited_urls(answer)
    if not references or any(unquote(url) in cited for url, _ in references):
        return answer, []
    english = language == "en" or (language == "auto" and not re.search(r"[\u4e00-\u9fff]", answer))
    lines = ["", "", "### Retrieved references (for verification)" if english else "### 本次检索资料（供核查）"]
    lines += ["", "These are retrieved sources, not proof of every claim above." if english else "以下为本次实际检索返回的资料，不代表每条均支持上述所有结论。", ""]
    for url, article in references[:3]:
        title = _label(article.get("title")) or ("Source" if english else "原文")
        source = _label(article.get("source"), 80) or urlsplit(url).hostname
        published = _label(article.get("published_at"), 60) or ("publication time unavailable" if english else "发布时间未提供")
        # Parentheses in paths must not terminate the Markdown link early.
        target = url.replace("(", "%28").replace(")", "%29")
        lines.append(f"- [{title}]({target}) — {source}；{published}")
    return answer + "\n".join(lines), ["news_reference_appendix_added"]
