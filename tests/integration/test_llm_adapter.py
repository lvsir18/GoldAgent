import asyncio

import httpx
import pytest
from langchain_core.messages import HumanMessage

from backend.app.llm.gateway import OpenAICompatibleGateway
from src.errors import ExternalProviderError


async def test_llm_adapter_parses_tool_calls(monkeypatch):
    payload = {
        "choices": [{"message": {"content": "", "tool_calls": [{"id": "1", "function": {"name": "price", "arguments": "{\"symbol\":\"AU0\"}"}}]}, "finish_reason": "tool_calls"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 3},
    }

    async def fake_post(self, *args, **kwargs):
        return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://llm.invalid/chat/completions"))

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    gateway = OpenAICompatibleGateway(provider="fixture", model="fixture", api_key="test", base_url="https://llm.invalid")
    result = await gateway.chat([HumanMessage(content="price")])
    assert result.tool_calls[0].name == "price"
    assert result.tool_calls[0].arguments == {"symbol": "AU0"}
    assert result.prompt_tokens == 10


async def test_llm_adapter_enforces_total_timeout(monkeypatch):
    async def slow_post(self, *args, **kwargs):
        await asyncio.sleep(0.05)
        return httpx.Response(200, json={"choices": []}, request=httpx.Request("POST", "https://llm.invalid/chat/completions"))

    monkeypatch.setattr(httpx.AsyncClient, "post", slow_post)
    gateway = OpenAICompatibleGateway(
        provider="fixture", model="fixture", api_key="test",
        base_url="https://llm.invalid", timeout_seconds=0.01,
    )
    with pytest.raises(ExternalProviderError, match="total timeout"):
        await gateway.chat([HumanMessage(content="price")])
