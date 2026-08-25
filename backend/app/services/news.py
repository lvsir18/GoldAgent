"""Real-time news service; no synthetic fallback articles."""

from ..providers.news.base import NewsProvider
from ..schemas.news import NewsSearchResult


class NewsService:
    def __init__(self, provider: NewsProvider):
        self.provider = provider

    async def search(self, query: str, max_results: int = 10) -> NewsSearchResult:
        cleaned = " ".join(query.split()).strip()
        if len(cleaned) < 2:
            raise ValueError("News query is too short")
        return await self.provider.search(cleaned, max_results=max_results)

