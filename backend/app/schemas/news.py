"""News schemas."""

from datetime import datetime, timezone

from pydantic import AnyHttpUrl, BaseModel, Field


class NewsArticle(BaseModel):
    title: str
    summary: str = ""
    source: str
    url: AnyHttpUrl | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sentiment: str | None = None
    impact: str | None = None


class NewsSearchResult(BaseModel):
    query: str
    articles: list[NewsArticle]
    source: str = "Tavily"
    is_stale: bool = False

