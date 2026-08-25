"""Authentication, request tracing and bounded in-memory demo rate limiting."""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ..core.security import TokenService

logger = logging.getLogger("goldagent.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.user_id = None
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            try:
                request.state.user_id = TokenService(request.app.state.settings.security).decode_access(authorization[7:])
            except ValueError:
                pass
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(json.dumps({"event":"http_request","request_id":request_id,"user_id":request.state.user_id,"method":request.method,"path":request.url.path,"status":response.status_code,"duration_ms":duration_ms},ensure_ascii=False))
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, default_limit: int = 120, window_seconds: int = 60):
        super().__init__(app); self.default_limit=default_limit; self.window_seconds=window_seconds; self.events=defaultdict(deque)
        self.expensive={"/api/v1/chat":20,"/api/v1/chat/stream":20,"/api/v1/forecasts":20,"/api/v1/backtests":10,"/api/v1/market/refresh":10,"/api/v1/news/refresh":10,"/api/v1/knowledge/documents":10}

    async def dispatch(self, request: Request, call_next):
        path=request.url.path; limit=next((value for prefix,value in self.expensive.items() if path.startswith(prefix)),self.default_limit)
        identity=request.headers.get("Authorization") or (request.client.host if request.client else "unknown"); key=(identity,path); now=time.monotonic(); events=self.events[key]
        while events and events[0] <= now-self.window_seconds: events.popleft()
        if len(events)>=limit: return JSONResponse(status_code=429,content={"success":False,"error":{"code":"RATE_LIMITED","message":"Too many requests"}},headers={"Retry-After":str(self.window_seconds)})
        events.append(now); return await call_next(request)
