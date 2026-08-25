"""Async Tavily provider."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.errors import ExternalProviderError

from ...schemas.news import NewsArticle, NewsSearchResult


class TavilyNewsProvider:
    lookback_hours = 72
    fallback_hours = 14 * 24

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 30):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.timeout_seconds = timeout_seconds
        self.endpoint = "https://api.tavily.com/search"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.25, min=0.25, max=2),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    async def search(self, query: str, max_results: int = 10) -> NewsSearchResult:
        if not self.api_key:
            raise ExternalProviderError("tavily", "TAVILY_API_KEY is not configured")
        result_limit = min(max(int(max_results), 1), 20)
        payload = {
            "api_key": self.api_key,
            "query": query,
            "topic": "news",
            # Tavily has no exact 72-hour preset. Fetch a one-week candidate
            # window, then enforce the rolling cutoff below.
            "time_range": "week",
            "search_depth": "basic",
            "max_results": 20,
            "include_answer": False,
            "include_raw_content": False,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                items = response.json().get("results", [])
                articles = self._recent_articles(items, self.lookback_hours, result_limit)
                if len(articles) < result_limit:
                    fallback_payload = {**payload, "time_range": "month"}
                    fallback_response = await client.post(self.endpoint, json=fallback_payload)
                    fallback_response.raise_for_status()
                    fallback_items = fallback_response.json().get("results", [])
                    articles = self._fill_with_fallback(
                        articles, fallback_items, result_limit,
                    )
        except httpx.HTTPError as exc:
            raise ExternalProviderError("tavily", f"News search failed: {type(exc).__name__}") from exc
        return NewsSearchResult(query=query, articles=articles)

    def _recent_articles(
        self, items: list[dict], lookback_hours: int, result_limit: int,
    ) -> list[NewsArticle]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        articles: list[NewsArticle] = []
        for item in items:
            if not item.get("title") or not item.get("published_date"):
                continue
            published_at = self._parse_published_at(item["published_date"])
            if published_at is None or published_at < cutoff:
                continue
            article = NewsArticle(
                title=str(item["title"]),
                summary=str(item.get("content", "")),
                source=self._publisher_from_url(item.get("url")),
                url=item.get("url") or None,
                published_at=published_at,
            )
            articles.append(article)
            if len(articles) >= result_limit:
                break
        return articles

    def _fill_with_fallback(
        self, primary: list[NewsArticle], items: list[dict], result_limit: int,
    ) -> list[NewsArticle]:
        seen = {str(article.url) if article.url else article.title for article in primary}
        combined = list(primary)
        candidate_groups = (
            self._recent_articles(items, self.lookback_hours, 20),
            self._recent_articles(items, self.fallback_hours, 20),
        )
        for candidates in candidate_groups:
            for article in candidates:
                identity = str(article.url) if article.url else article.title
                if identity in seen:
                    continue
                combined.append(article)
                seen.add(identity)
                if len(combined) >= result_limit:
                    return combined
        return combined

    @staticmethod
    def _publisher_from_url(url: str | None) -> str:
        hostname = urlparse(url or "").hostname or ""
        return hostname.removeprefix("www.") or "Tavily"

    @staticmethod
    def _parse_published_at(value: object) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError, OverflowError):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (TypeError, ValueError, OverflowError):
                    return None
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
