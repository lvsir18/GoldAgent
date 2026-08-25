"""Provider-neutral LLM gateway contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, TypeVar

from langchain_core.messages import BaseMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ChatResponse:
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    finish_reason: str | None = None


class LLMGateway(Protocol):
    async def chat(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> ChatResponse: ...

    async def stream(self, messages: list[BaseMessage], tools: list[BaseTool] | None = None) -> AsyncIterator[str]: ...

    def bind_tools(self, tools: list[BaseTool]) -> "LLMGateway": ...

    async def structured_output(self, messages: list[BaseMessage], schema: type[SchemaT]) -> SchemaT: ...

