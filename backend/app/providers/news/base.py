"""News provider contract."""

from typing import Protocol

from ...schemas.news import NewsSearchResult


class NewsProvider(Protocol):
    async def search(self, query: str, max_results: int = 10) -> NewsSearchResult:
        """Search current news without fabricating fallback articles."""

