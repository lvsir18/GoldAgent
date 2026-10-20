"""Real-time news service; no synthetic fallback articles."""

from ..providers.news.base import NewsProvider
from ..schemas.news import NewsSearchResult
import re


def clean_news_summary(text: str) -> str:
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[#*_`>|]+", " ", text)
    return " ".join(text.split())[:800]


class NewsService:
    def __init__(self, provider: NewsProvider):
        self.provider = provider

    async def search(self, query: str, max_results: int = 10) -> NewsSearchResult:
        cleaned = " ".join(query.split()).strip()
        if len(cleaned) < 2:
            raise ValueError("News query is too short")
        result = await self.provider.search(cleaned, max_results=max_results)
        seen, articles = set(), []
        for article in result.articles:
            key = re.sub(r"\W+", "", article.title.lower())
            if not key or key in seen:
                continue
            seen.add(key)
            articles.append(article.model_copy(update={"summary": clean_news_summary(article.summary)}))
        return result.model_copy(update={"articles": articles})

