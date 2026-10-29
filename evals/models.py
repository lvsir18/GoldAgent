"""Versioned contracts for synthetic, reproducible Agent evaluation."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ArgumentCheck(BaseModel):
    tool: str
    field: str
    value: Any = None
    minimum: float | None = None
    maximum: float | None = None
    contains: str | None = None


class NumericAnswerCheck(BaseModel):
    pattern: str
    expected: float
    tolerance: float = Field(default=.01, ge=0)


class NumericOutputCheck(BaseModel):
    tool: str
    field: str
    expected: float
    tolerance: float = Field(default=.01, ge=0)


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    category: str
    query: str
    expected_tools: list[str] = Field(default_factory=list)
    optional_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    alternative_tool_groups: list[list[str]] = Field(default_factory=list)
    expected_source_types: list[str] = Field(default_factory=list)
    require_disclaimer: bool = False
    forbidden_patterns: list[str] = Field(default_factory=list)
    answer_patterns: list[str] = Field(default_factory=list)
    forbidden_answer_patterns: list[str] = Field(default_factory=list)
    argument_checks: list[ArgumentCheck] = Field(default_factory=list)
    tool_order: list[list[str]] = Field(default_factory=list)
    expected_errors: list[str] = Field(default_factory=list)
    require_url_citation: bool = False
    require_document_citation: bool = False
    max_duplicate_calls: int = 0
    behavior: Literal["answer", "clarify", "refuse", "graceful_failure"] = "answer"
    scenario: Literal["normal", "market_down", "news_down", "empty_knowledge", "short_history", "injection", "stale_market"] = "normal"
    portfolio: dict[str, Any] | None = None
    risk_profile: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, str]] = Field(default_factory=list)
    as_of: str = "2026-10-29T06:00:00+00:00"
    review_required: bool = True
    provided_price: float | None = Field(default=None, gt=0)
    language: Literal["zh", "en", "auto"] = "zh"
    numeric_answer_checks: list[NumericAnswerCheck] = Field(default_factory=list)
    numeric_output_checks: list[NumericOutputCheck] = Field(default_factory=list)
    max_cited_news_age_hours: int = Field(default=336, ge=1)


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str
    sample_id: int = Field(default=1, ge=1)
    answer: str
    tool_calls: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    status: str = "completed"
    success: bool | None = None  # Legacy recordings; false always fails acceptance.
    latency_ms: float = Field(default=0, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0)
    metrics: dict = Field(default_factory=dict)
    error_code: str | None = None


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""


class EvaluationResult(BaseModel):
    case_id: str
    sample_id: int = 1
    category: str
    task_success: float
    tool_selection_accuracy: float
    tool_argument_accuracy: float
    tool_execution_success: float | None
    source_accuracy: float | None
    citation_accuracy: float | None
    answer_contract: float
    hallucination_proxy: float
    financial_safety: float
    latency_ms: float
    token_usage: int | None
    cost: float | None
    duplicate_calls: int
    model_calls: int
    protocol_repairs: int
    failures: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    manual_review: str = "pending"
