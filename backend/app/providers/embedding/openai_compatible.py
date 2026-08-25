"""Async OpenAI-compatible embedding adapter."""

import httpx

from src.errors import ExternalProviderError


class OpenAICompatibleEmbeddingProvider:
    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int = 384):
        self.api_key, self.base_url, self.model = api_key, base_url.rstrip("/"), model
        self.dimensions, self.name = dimensions, f"openai_compatible:{model}"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(f"{self.base_url}/embeddings", headers={"Authorization": f"Bearer {self.api_key}"}, json={"model": self.model, "input": texts, "dimensions": self.dimensions})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalProviderError("embedding", f"Embedding request failed: {type(exc).__name__}") from exc
        items = sorted(response.json().get("data", []), key=lambda item: item.get("index", 0))
        vectors = [item["embedding"] for item in items]
        if len(vectors) != len(texts):
            raise ExternalProviderError("embedding", "Embedding result count mismatch")
        return vectors
