from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request):
    checks = {
        "api": True,
        "database": False,
        "llm_config": bool(request.app.state.settings.llm_api_key()),
        "market_provider": True,
        "checkpointer": hasattr(request.app.state, "checkpointer"),
    }
    try:
        async with request.app.state.database.session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
        if request.app.state.settings.database.url.startswith("postgresql"):
            async with request.app.state.database.session() as session:
                checks["vector_extension"] = bool(await session.scalar(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')")))
        else:
            checks["vector_extension"] = "demo_sqlite"
    except Exception:
        pass
    vector_ready = checks.get("vector_extension") in {True, "demo_sqlite"}
    llm_ready = checks["llm_config"] or request.app.state.settings.security.demo_mode
    status = "ready" if checks["database"] and checks["market_provider"] and checks["checkpointer"] and vector_ready and llm_ready else "not_ready"
    return {"status": status, "checks": checks}
