from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx

from backend.app.providers.news.tavily import TavilyNewsProvider


async def test_tavily_news_uses_rolling_72_hour_window(monkeypatch):
    now = datetime.now(timezone.utc)
    captured_payloads = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            if self.payload["time_range"] == "week":
                return {
                "results": [
                    {
                        "title": "Recent gold news",
                        "content": "Recent content",
                        "url": "https://www.finance.example.com/gold/recent",
                        "published_date": format_datetime(now - timedelta(hours=2)),
                        "score": 0.9,
                    },
                    {
                        "title": "Old gold news",
                        "content": "Old content",
                        "url": "https://old.example.com/gold",
                        "published_date": format_datetime(now - timedelta(hours=73)),
                        "score": 0.95,
                    },
                    {
                        "title": "Undated gold news",
                        "content": "Missing publication date",
                        "url": "https://unknown.example.com/gold",
                    },
                ]
                }
            return {
                "results": [
                    {
                        "title": "Recent gold news",
                        "content": "Duplicate recent content",
                        "url": "https://www.finance.example.com/gold/recent",
                        "published_date": format_datetime(now - timedelta(hours=2)),
                    },
                    {
                        "title": "Fallback gold news",
                        "content": "Older but still timely content",
                        "url": "https://fallback.example.com/gold",
                        "published_date": format_datetime(now - timedelta(days=8)),
                    },
                    {
                        "title": "Fresh fallback gold news",
                        "content": "Fresh result missed by the first search",
                        "url": "https://fresh.example.com/gold",
                        "published_date": format_datetime(now - timedelta(hours=4)),
                    },
                    {
                        "title": "Expired gold news",
                        "content": "Too old",
                        "url": "https://expired.example.com/gold",
                        "published_date": format_datetime(now - timedelta(days=15)),
                    },
                ]
            }

    async def fake_post(self, url, json):
        captured_payloads.append(json)
        return FakeResponse(json)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await TavilyNewsProvider(api_key="test-key").search("gold", max_results=10)

    assert captured_payloads[0]["topic"] == "news"
    assert captured_payloads[0]["time_range"] == "week"
    assert captured_payloads[0]["include_answer"] is False
    assert captured_payloads[1]["time_range"] == "month"
    assert [article.title for article in result.articles] == [
        "Recent gold news", "Fresh fallback gold news", "Fallback gold news",
    ]
    assert result.articles[0].source == "finance.example.com"
    assert result.articles[0].published_at is not None
