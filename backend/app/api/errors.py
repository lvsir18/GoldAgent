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
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, exc.code, exc.message, exc.details),
    )


async def http_error_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=_payload(request, "HTTP_ERROR", str(exc.detail)))


async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=_payload(request, "VALIDATION_ERROR", "Request validation failed", {"errors": exc.errors()}))


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled_request_error", extra={"request_id": getattr(request.state, "request_id", None)})
    return JSONResponse(
        status_code=500,
        content=_payload(request, "INTERNAL_ERROR", "Unexpected server error"),
    )
