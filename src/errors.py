"""Shared structured errors for legacy and GoldAgent adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class GoldAgentError(Exception):
    """Base domain error with a stable machine-readable code."""

    code: str
    message: str
    status_code: int = 500
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class ConfigurationError(GoldAgentError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__("CONFIGURATION_ERROR", message, 500, details)


class InvalidIdentifierError(GoldAgentError):
    def __init__(self, kind: str):
        super().__init__("INVALID_IDENTIFIER", f"Invalid {kind} identifier", 400)


class MarketDataUnavailableError(GoldAgentError):
    def __init__(self, message: str = "Market data is unavailable"):
        super().__init__("MARKET_DATA_UNAVAILABLE", message, 503)


class ExternalProviderError(GoldAgentError):
    def __init__(self, provider: str, message: str):
        super().__init__("EXTERNAL_PROVIDER_ERROR", message, 502, {"provider": provider})
