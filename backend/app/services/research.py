"""Build verifiable artifacts from tool outputs, never from invented LLM facts."""
from typing import Any
from urllib.parse import urlparse
from ..core.presentation import tool_name


def research_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    citations, snapshots, limitations = [], [], []
    seen: set[str] = set()
    for item in results:
        output = item.get("output") or {}
        if item.get("error"):
            limitations.append(f"{tool_name(item['tool'])}暂时获取失败，相关结论可能不完整，请稍后重试")
        if not isinstance(output, dict):
            continue
        metadata = output.get("metadata") or {}
        if metadata:
            snapshots.append({"tool": item["tool"], "metadata": metadata})
            if metadata.get("is_stale"):
                limitations.append(f"{tool_name(item['tool'])}使用了较早数据，请核查最新变化")
            if metadata.get("source_type") == "derived":
                limitations.append(f"{tool_name(item['tool'])}为换算参考行情，不是直接交易报价")
        for article in output.get("articles", []):
            url = article.get("url", "")
            if urlparse(url).scheme in {"http", "https"} and url not in seen:
                seen.add(url)
                citations.append({"title": article.get("title", url), "url": url,
                    "source": article.get("source"), "published_at": article.get("published_at")})
        for chunk in output.get("results", []):
            if chunk.get("chunk_id"):
                citations.append({"title": chunk.get("metadata", {}).get("filename", "Knowledge"),
                    "document_id": chunk.get("document_id"), "chunk_id": chunk["chunk_id"],
                    "page": chunk.get("metadata", {}).get("page"), "source": "Knowledge Base"})
    if not results:
        limitations.append("本次回答未调用外部资料，不能视为实时行情分析。")
    return {"schema_version": 1, "citations": citations, "snapshots": snapshots, "limitations": limitations}
