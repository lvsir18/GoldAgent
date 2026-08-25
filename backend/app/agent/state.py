"""Serializable LangGraph state; large DataFrames are deliberately excluded."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GoldAgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    session_id: str
    run_id: str
    intent: str | None
    plan: list[str]
    market_context: dict[str, Any] | None
    technical_context: dict[str, Any] | None
    news_context: list[dict[str, Any]] | None
    rag_context: list[dict[str, Any]] | None
    portfolio_context: dict[str, Any] | None
    forecast_context: dict[str, Any] | None
    tool_results: list[dict[str, Any]]
    current_step: int
    max_steps: int
    retry_count: int
    data_freshness: str | None
    risk_level: str | None
    verification_result: dict[str, Any] | None
    final_answer: str | None
    status: str

