"""GoldAgent FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from src.errors import GoldAgentError
from src.settings import AppSettings

from ..core.container import build_container
from ..db.repositories import UserRepository
from ..db.session import build_database
from ..rag import build_knowledge_service
from ..memory.checkpoint import checkpointer_context
from .errors import goldagent_error_handler, http_error_handler, unhandled_error_handler, validation_error_handler
from .routes import api_router, health_router
from .middleware import RateLimitMiddleware, RequestContextMiddleware
from ..observability import configure_structured_logging


def create_app(settings: AppSettings | None = None) -> FastAPI:
    root = Path(__file__).resolve().parents[3]
    resolved_settings = settings or AppSettings.load(root / "config.yaml")
    configure_structured_logging(str(resolved_settings.logging.get("level", "INFO")))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = resolved_settings
        app.state.services = build_container(resolved_settings)
        app.state.database = build_database(resolved_settings)
        await app.state.database.create_all()
        await app.state.database.recover_interrupted_agent_runs()
        app.state.knowledge = build_knowledge_service(resolved_settings, app.state.database)
        if resolved_settings.security.demo_mode:
            async with app.state.database.session() as session:
                await UserRepository(session).ensure_demo_user()
        try:
            async with checkpointer_context(resolved_settings) as checkpointer:
                app.state.checkpointer = checkpointer
                yield
        finally:
            await app.state.database.dispose()

    app = FastAPI(title="GoldAgent API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.security.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(
        RateLimitMiddleware,
        default_limit=resolved_settings.security.rate_limit_per_minute,
        window_seconds=60,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(GoldAgentError, goldagent_error_handler)
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api/v1")
    return app
