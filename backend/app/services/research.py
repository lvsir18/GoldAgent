"""Build verifiable artifacts from tool outputs, never from invented LLM facts."""
from typing import Any
from urllib.parse import urlparse


def research_evidence(results: list[dict[str, Any]]) -> dict[str, Any]:
    citations, snapshots, limitations = [], [], []
    seen: set[str] = set()
    for item in results:
        output = item.get("output") or {}
        if item.get("error"):
            limitations.append(f"{item['tool']}: {item['error']}")
        if not isinstance(output, dict):
            continue
        metadata = output.get("metadata") or {}
        if metadata:
            snapshots.append({"tool": item["tool"], "metadata": metadata})
            if metadata.get("is_stale"):
                limitations.append(f"{item['tool']}: cached/stale data")
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
        limitations.append("No tools were used; this response is not a live market assessment.")
    return {"schema_version": 1, "citations": citations, "snapshots": snapshots, "limitations": limitations}
