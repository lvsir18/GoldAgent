"""Structured error responses."""

import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.errors import GoldAgentError

logger = logging.getLogger("goldagent.api")


def _payload(request: Request, code: str, message: str, details=None):
    return {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
        "meta": {"request_id": getattr(request.state, "request_id", None)},
    }


async def goldagent_error_handler(request: Request, exc: GoldAgentError):
    logger.warning("domain_request_error", extra={"request_id": getattr(request.state, "request_id", None), "code": exc.code})
    messages = {
        "MARKET_DATA_UNAVAILABLE": "Market data is temporarily unavailable. Please retry later.",
        "CONFIGURATION_ERROR": "This feature is not configured. Contact the site maintainer.",
        "EXTERNAL_PROVIDER_ERROR": "A data service is temporarily unavailable. Please retry later.",
        "INVALID_IDENTIFIER": "This item is unavailable. Refresh the list and retry.",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, exc.code, messages.get(exc.code, "This action could not be completed. Please retry later.")),
    )


async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=_payload(request, "HTTP_ERROR", str(exc.detail)))


async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(map(str, item["loc"])), "type": item["type"]} for item in exc.errors()]
    return JSONResponse(status_code=422, content=_payload(request, "VALIDATION_ERROR", "Check the input format and parameter ranges", {"errors": fields}))


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_request_error", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(
        status_code=500,
        content=_payload(request, "INTERNAL_ERROR", "Unexpected server error"),
    )
