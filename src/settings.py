"""Typed application settings with duplicate-YAML-key detection."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from dotenv import load_dotenv
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator

from .errors import ConfigurationError, GoldAgentError


class _StrictYamlLoader(yaml.SafeLoader):
    pass


def _construct_mapping(loader: _StrictYamlLoader, node: yaml.MappingNode, deep: bool = False):
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConfigurationError(f"Duplicate YAML key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_StrictYamlLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class TimeRangeSettings(FlexibleModel):
    period: str = "3y"


class DataSettings(FlexibleModel):
    time_range: TimeRangeSettings = Field(default_factory=TimeRangeSettings)
    international: dict[str, Any] = Field(default_factory=dict)
    domestic: dict[str, Any] = Field(default_factory=dict)


class ProcessingSettings(FlexibleModel):
    timezone: str = "Asia/Shanghai"
    remove_weekends: bool = True
    fill_missing: Literal["forward", "backward", "interpolate"] = "forward"
    strategy_mode: str = "icbc_accumulation_gold"
    resample_freq: Literal["D", "W", "M"] = "W"
    basis_adjustment: float = Field(default=0.995, gt=0, le=1.5)
    premium_fx_rate: float = Field(default=7.2, gt=0)


class AgentSettings(FlexibleModel):
    provider: str = "mimo"
    model: str = "mimo-v2.5-pro"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=4096, gt=0, le=131072)
    top_p: float = Field(default=0.9, gt=0, le=1)
    api_url: AnyHttpUrl = "https://api.xiaomimimo.com/v1"
    api_endpoint: str = "/chat/completions"
    request_timeout_seconds: int = Field(default=120, ge=1, le=600)
    run_timeout_seconds: int = Field(default=300, ge=10, le=1800)
    max_steps: int = Field(default=12, ge=1, le=50)
    tool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_tool_retries: int = Field(default=2, ge=0, le=10)

    @field_validator("api_endpoint")
    @classmethod
    def endpoint_starts_with_slash(cls, value: str) -> str:
        return value if value.startswith("/") else f"/{value}"


class ForecastSettings(FlexibleModel):
    periods: int = Field(default=3, ge=1, le=30)
    method: Literal["linear", "ma", "exponential"] = "exponential"
    ma_window: int = Field(default=5, ge=2, le=365)
    exponential_alpha: float = Field(default=0.3, gt=0, le=1)


class TavilySettings(FlexibleModel):
    timeout: int = Field(default=60, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=10)
    max_results: int = Field(default=10, ge=1, le=50)


class DatabaseSettings(FlexibleModel):
    url: str = "sqlite:///data/goldagent.db"
    echo: bool = False


class SecuritySettings(FlexibleModel):
    demo_mode: bool = True
    frontend_origins: list[str] = Field(default_factory=list)
    access_token_minutes: int = Field(default=30, ge=1)
    refresh_token_days: int = Field(default=7, ge=1)
    jwt_secret_key: str = "change-me-in-production"
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10_000)


class AppSettings(FlexibleModel):
    data: DataSettings = Field(default_factory=DataSettings)
    processing: ProcessingSettings = Field(default_factory=ProcessingSettings)
    indicators: dict[str, Any] = Field(default_factory=dict)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    rag: dict[str, Any] = Field(default_factory=dict)
    tavily: TavilySettings = Field(default_factory=TavilySettings)
    forecast: ForecastSettings = Field(default_factory=ForecastSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    output: dict[str, Any] = Field(default_factory=dict)
    logging: dict[str, Any] = Field(default_factory=dict)
    chat: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path) -> "AppSettings":
        load_dotenv(config_path.parent / ".env", override=False)
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                raw = yaml.load(handle, Loader=_StrictYamlLoader) or {}
        except GoldAgentError:
            raise
        except Exception as exc:
            raise ConfigurationError(f"Unable to load {config_path}: {exc}") from exc

        raw.setdefault("agent", {})
        raw["agent"]["provider"] = os.getenv("LLM_PROVIDER", raw["agent"].get("provider", "mimo"))
        raw["agent"]["model"] = os.getenv("MIMO_MODEL", raw["agent"].get("model", "mimo-v2.5-pro"))
        raw["agent"]["api_url"] = os.getenv("MIMO_BASE_URL", raw["agent"].get("api_url"))
        raw.setdefault("database", {})
        raw["database"]["url"] = os.getenv("DATABASE_URL", raw["database"].get("url", "sqlite:///data/goldagent.db"))
        raw.setdefault("security", {})
        if os.getenv("DEMO_MODE") is not None:
            raw["security"]["demo_mode"] = os.getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes"}
        if os.getenv("FRONTEND_ORIGINS"):
            raw["security"]["frontend_origins"] = [item.strip() for item in os.environ["FRONTEND_ORIGINS"].split(",") if item.strip()]
        raw["security"]["jwt_secret_key"] = os.getenv("JWT_SECRET_KEY", raw["security"].get("jwt_secret_key", "change-me-in-production"))
        if not raw["security"].get("demo_mode") and raw["security"]["jwt_secret_key"] == "change-me-in-production":
            raise ConfigurationError("JWT_SECRET_KEY must be changed outside DEMO_MODE")
        return cls.model_validate(raw)

    def llm_api_key(self) -> str | None:
        provider = self.agent.provider.lower()
        provider_key = {"mimo": "MIMO_API_KEY", "openai": "OPENAI_API_KEY", "qwen": "DASHSCOPE_API_KEY"}.get(provider)
        candidates = [provider_key, "LLM_API_KEY", "MIMO_API_KEY", "DASHSCOPE_API_KEY"]
        return next((os.getenv(name) for name in candidates if name and os.getenv(name)), None)
