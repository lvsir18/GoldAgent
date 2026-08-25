"""OpenAI-compatible async adapter used by MiMo and alternative providers."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import replace
from typing import Any, AsyncIterator, TypeVar

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.errors import ConfigurationError, ExternalProviderError
from src.settings import AppSettings

from .base import ChatResponse, LLMGateway, ToolCall

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _message_payload(message: BaseMessage) -> dict[str, Any]:
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": str(message.content)}
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": str(message.content)}
    if isinstance(message, ToolMessage):
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": str(message.content)}
    if isinstance(message, AIMessage):
        payload: dict[str, Any] = {"role": "assistant", "content": str(message.content or "")}
        if message.tool_calls:
            payload["tool_calls"] = [
                {
                    "id": call.get("id") or str(uuid.uuid4()),
                    "type": "function",
                    "function": {"name": call["name"], "arguments": json.dumps(call.get("args", {}), ensure_ascii=False)},
                }
                for call in message.tool_calls
            ]
        return payload
    return {"role": "user", "content": str(message.content)}


def _tool_payload(tool: BaseTool) -> dict[str, Any]:
    schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {"name": tool.name, "description": tool.description, "parameters": schema},
    }


class OpenAICompatibleGateway(LLMGateway):
    def __init__(
        self, *, provider: str, model: str, api_key: str, base_url: str,
        temperature: float = 0.2, max_tokens: int = 4096, timeout_seconds: int = 120,
        bound_tools: list[BaseTool] | None = None,
    ):
        if not api_key:
            raise ConfigurationError(f"API key for provider '{provider}' is not configured")
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.bound_tools = bound_tools
        self.last_latency_ms: float | None = None

    def bind_tools(self, tools: list[BaseTool]) -> "OpenAICompatibleGateway":
        return OpenAICompatibleGateway(
            provider=self.provider, model=self.model, api_key=self.api_key, base_url=self.base_url,
            temperature=self.temperature, max_tokens=self.max_tokens, timeout_seconds=self.timeout_seconds,
            bound_tools=tools,
        )

    def _payload(self, messages: list[BaseMessage], tools: list[BaseTool] | None, stream: bool = False) -> dict[str, Any]:
        selected_tools = tools if tools is not None else self.bound_tools
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_message_payload(message) for message in messages],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if selected_tools:
            payload["tools"] = [_tool_payload(tool) for tool in selected_tools]
            payload["tool_choice"] = "auto"
        return payload

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)), reraise=True,
    )
    async def chat(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> ChatResponse:
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=self._payload(messages, tools),
                    )
                    response.raise_for_status()
        except TimeoutError as exc:
            raise ExternalProviderError(
                self.provider,
                f"LLM request exceeded the {self.timeout_seconds}s total timeout",
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalProviderError(self.provider, f"LLM request failed: {type(exc).__name__}") from exc
        finally:
            self.last_latency_ms = (time.perf_counter() - started) * 1000
        payload = response.json()
        choice = payload.get("choices", [{}])[0]
        message = choice.get("message", {})
        calls = []
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError:
                arguments = {}
            calls.append(ToolCall(id=call.get("id") or str(uuid.uuid4()), name=function.get("name", ""), arguments=arguments))
        usage = payload.get("usage", {})
        return ChatResponse(
            content=str(message.get("content") or ""), tool_calls=calls,
            prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
        )

    async def stream(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    async with client.stream(
                        "POST", f"{self.base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=self._payload(messages, tools, stream=True),
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                break
                            try:
                                delta = json.loads(data).get("choices", [{}])[0].get("delta", {}).get("content")
                            except (json.JSONDecodeError, IndexError):
                                continue
                            if delta:
                                yield str(delta)
        except TimeoutError as exc:
            raise ExternalProviderError(
                self.provider,
                f"LLM stream exceeded the {self.timeout_seconds}s total timeout",
            ) from exc
        except httpx.HTTPError as exc:
            raise ExternalProviderError(self.provider, f"LLM stream failed: {type(exc).__name__}") from exc

    async def structured_output(self, messages: list[BaseMessage], schema: type[SchemaT]) -> SchemaT:
        schema_instruction = SystemMessage(
            content=f"Return JSON only, matching this schema: {json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
        )
        response = await self.chat([schema_instruction, *messages])
        raw = response.content.strip().removeprefix("```json").removesuffix("```").strip()
        return schema.model_validate_json(raw)


def build_llm_gateway(settings: AppSettings) -> OpenAICompatibleGateway:
    key = settings.llm_api_key()
    if not key:
        raise ConfigurationError(f"No API key configured for LLM provider '{settings.agent.provider}'")
    return OpenAICompatibleGateway(
        provider=settings.agent.provider, model=settings.agent.model, api_key=key,
        base_url=str(settings.agent.api_url), temperature=settings.agent.temperature,
        max_tokens=settings.agent.max_tokens, timeout_seconds=settings.agent.request_timeout_seconds,
    )
