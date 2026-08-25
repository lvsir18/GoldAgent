"""Structured logging with explicit sensitive-field redaction."""

import json
import logging
from typing import Any

SENSITIVE = {"api_key", "authorization", "password", "token", "refresh_token", "access_token"}


def redact(value: Any):
    if isinstance(value, dict): return {key: "<redacted>" if key.lower() in SENSITIVE else redact(item) for key,item in value.items()}
    if isinstance(value, list): return [redact(item) for item in value]
    return value


def log_event(logger: logging.Logger, event: str, **fields):
    logger.info(json.dumps({"event":event,**redact(fields)},ensure_ascii=False,default=str))


def configure_structured_logging(level: str = "INFO"):
    logging.basicConfig(level=getattr(logging,level.upper(),logging.INFO),format="%(message)s")
