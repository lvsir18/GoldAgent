"""OpenAI-compatible async adapter used by MiMo and alternative providers."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
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
        if message.additional_kwargs.get("reasoning_content"):
            payload["reasoning_content"] = message.additional_kwargs["reasoning_content"]
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
        thinking: str | None = None, planning_max_tokens: int = 1024,
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
        self.thinking, self.planning_max_tokens = thinking, planning_max_tokens
        self.last_latency_ms: float | None = None
        self._client: httpx.AsyncClient | None = None

    @asynccontextmanager
    async def session(self):
        """One HTTP connection pool per run, never shared across users."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            self._client = client
            try:
                yield
            finally:
                self._client = None

    @asynccontextmanager
    async def _http_client(self):
        if self._client is not None:
            yield self._client
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                yield client

    def bind_tools(self, tools: list[BaseTool]) -> "OpenAICompatibleGateway":
        return OpenAICompatibleGateway(
            provider=self.provider, model=self.model, api_key=self.api_key, base_url=self.base_url,
            temperature=self.temperature, max_tokens=self.max_tokens, timeout_seconds=self.timeout_seconds,
            bound_tools=tools,
            thinking=self.thinking, planning_max_tokens=self.planning_max_tokens,
        )

    def for_phase(self, phase: str) -> "OpenAICompatibleGateway":
        gateway = OpenAICompatibleGateway(provider=self.provider, model=self.model, api_key=self.api_key,
            base_url=self.base_url, temperature=self.temperature,
            max_tokens=min(self.max_tokens, self.planning_max_tokens) if phase == "plan" else self.max_tokens,
            timeout_seconds=self.timeout_seconds, bound_tools=None,
            thinking="disabled" if phase == "plan" else "enabled", planning_max_tokens=self.planning_max_tokens)
        gateway._client = self._client
        return gateway

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
        if self.provider == "mimo":
            # MiMo documents max_completion_tokens as the joint visible/reasoning
            # budget. Do not rely on a legacy max_tokens alias being respected.
            payload["max_completion_tokens"] = payload.pop("max_tokens")
            if self.thinking is not None:
                payload["thinking"] = {"type": self.thinking}
            if self.thinking != "disabled":
                payload.pop("temperature", None)
        else:
            for message in payload["messages"]:
                message.pop("reasoning_content", None)
        return payload

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)), reraise=True,
    )
    async def chat(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> ChatResponse:
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self._http_client() as client:
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
        calls, protocol_error = [], None
        raw_calls = message.get("tool_calls") or []
        if not isinstance(raw_calls, list):
            raw_calls, protocol_error = [], "invalid_tool_calls_shape"
        for call in raw_calls:
            if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
                protocol_error = "invalid_tool_calls_shape"
                continue
            function = call["function"]
            raw_arguments = function.get("arguments", "{}")
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError:
                arguments = {}
                protocol_error = "invalid_tool_arguments"
            if not isinstance(arguments, dict):
                arguments, protocol_error = {}, "invalid_tool_arguments"
            calls.append(ToolCall(id=call.get("id") or str(uuid.uuid4()), name=function.get("name", ""), arguments=arguments))
        usage = payload.get("usage", {})
        return ChatResponse(
            content=str(message.get("content") or ""), tool_calls=calls,
            prompt_tokens=usage.get("prompt_tokens"), completion_tokens=usage.get("completion_tokens"),
            finish_reason=choice.get("finish_reason"),
            reasoning_content=message.get("reasoning_content"),
            reasoning_tokens=(usage.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            cached_tokens=(usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
            protocol_error=protocol_error,
        )

    async def stream(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> AsyncIterator[str]:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self._http_client() as client:
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
        planning_max_tokens=settings.agent.planning_max_tokens,
    )
