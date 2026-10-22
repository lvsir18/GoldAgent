import asyncio

import httpx
import pytest
from langchain_core.messages import HumanMessage, AIMessage

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


async def test_mimo_phase_controls_and_reasoning_replay(monkeypatch):
    captured = []
    async def fake_post(self,*args,**kwargs):
        captured.append(kwargs["json"])
        return httpx.Response(200,json={"choices":[{"message":{"content":"answer","reasoning_content":"PRIVATE"},"finish_reason":"stop"}],"usage":{"completion_tokens_details":{"reasoning_tokens":9},"prompt_tokens_details":{"cached_tokens":4}}},request=httpx.Request("POST","https://llm.invalid/chat/completions"))
    monkeypatch.setattr(httpx.AsyncClient,"post",fake_post)
    gateway = OpenAICompatibleGateway(provider="mimo",model="mimo-v2.6-pro",api_key="test",base_url="https://llm.invalid",max_tokens=4096)
    response = await gateway.for_phase("plan").chat([HumanMessage(content="test")])
    assert captured[-1]["thinking"] == {"type":"disabled"}
    assert captured[-1]["max_completion_tokens"] == 1024
    assert "max_tokens" not in captured[-1]
    assert response.reasoning_tokens == 9
    assert response.cached_tokens == 4
    assert "PRIVATE" not in repr(response)
    await gateway.for_phase("synthesize").chat([AIMessage(content="",additional_kwargs={"reasoning_content":"PRIVATE"})], [])
    assert captured[-1]["thinking"] == {"type":"enabled"}
    assert captured[-1]["max_completion_tokens"] == 4096
    assert "temperature" not in captured[-1]
    assert captured[-1]["messages"][0]["reasoning_content"] == "PRIVATE"
    assert "tools" not in captured[-1]


async def test_phase_calls_reuse_and_close_one_http_pool(monkeypatch):
    clients = []
    async def fake_post(self,*args,**kwargs):
        clients.append(self)
        return httpx.Response(200,json={"choices":[{"message":{"content":"ok"}}]},request=httpx.Request("POST","https://llm.invalid/chat/completions"))
    monkeypatch.setattr(httpx.AsyncClient,"post",fake_post)
    gateway = OpenAICompatibleGateway(provider="mimo",model="fixture",api_key="test",base_url="https://llm.invalid")
    async with gateway.session():
        await gateway.for_phase("plan").chat([HumanMessage(content="test")])
        await gateway.for_phase("synthesize").chat([HumanMessage(content="test")])
        assert clients[0] is clients[1]
        assert not clients[0].is_closed
    assert clients[0].is_closed
