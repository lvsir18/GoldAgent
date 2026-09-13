from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import suppress
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database
from ...agent.graph import build_agent_runtime
from ...db.models import PortfolioRecord, RiskProfile, ToolCallRecord, UserProfile
from ...db.repositories import AgentRunRepository, SessionRepository
from ...db.session import Database
from ...tools.registry import build_tool_registry

router = APIRouter(tags=["agent"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str | None = None


def session_title_from_message(message: str, limit: int = 36) -> str:
    """Create a compact, deterministic title from the first user question."""
    normalized = " ".join(message.split()).strip()
    if not normalized:
        return "新会话"
    return normalized if len(normalized) <= limit else f"{normalized[:limit].rstrip()}…"


async def _ensure_session(database: Database, user_id: str, session_id: str | None):
    async with database.session() as session:
        repository = SessionRepository(session, user_id)
        item = await repository.get(session_id) if session_id else None
        if session_id and not item:
            raise HTTPException(404, "Session not found")
        return item or await repository.create()


ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


async def _load_user_context(database: Database, user_id: str) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any] | None]:
    async with database.session() as session:
        portfolio = await session.scalar(select(PortfolioRecord).where(PortfolioRecord.user_id == user_id))
        profile = await session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        risk = await session.scalar(select(RiskProfile).where(RiskProfile.user_id == user_id))
    portfolio_context = None if portfolio is None else {
        "grams": portfolio.grams,
        "average_cost": portfolio.average_cost,
        "planned_investment": portfolio.planned_investment,
        "currency": portfolio.currency,
    }
    risk_context = None if risk is None else {
        "risk_level": risk.risk_level,
        "max_drawdown_pct": risk.max_drawdown_pct,
        "horizon": risk.horizon,
        "notes": risk.notes,
    }
    preferences = dict(profile.preferences or {}) if profile else {}
    if profile and profile.display_name:
        preferences["display_name"] = profile.display_name
    return portfolio_context, preferences, risk_context


async def _save_run_failure(
    database: Database, user_id: str, run_id: str, exc: BaseException, status: str,
) -> None:
    detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    async with database.session() as session:
        await AgentRunRepository(session, user_id).save_failure(run_id, detail, status)


async def _run(
    request: Request, body: ChatRequest, database: Database, user_id: str,
    *, run_id: str | None = None, on_event: ProgressCallback | None = None,
):
    session_item = await _ensure_session(database, user_id, body.session_id)
    run_id = run_id or str(uuid.uuid4())
    async with database.session() as session:
        sessions = SessionRepository(session, user_id)
        if not await sessions.messages(session_item.id):
            await sessions.rename(session_item.id, session_title_from_message(body.message))
        await sessions.add_message(session_item.id, "user", body.message)
        await AgentRunRepository(session, user_id).create(session_item.id, run_id)
    portfolio_context, user_preferences, risk_profile = await _load_user_context(database, user_id)
    runtime = build_agent_runtime(
        request.app.state.settings,
        tools=build_tool_registry(
            request.app.state.services, request.app.state.knowledge, user_id,
            portfolio_context=portfolio_context, risk_profile=risk_profile,
        ),
        checkpointer=request.app.state.checkpointer,
    )
    try:
        state = await runtime.invoke(
            user_message=body.message,
            user_id=user_id,
            session_id=session_item.id,
            run_id=run_id,
            on_event=on_event,
            portfolio_context=portfolio_context,
            user_preferences=user_preferences,
            risk_profile=risk_profile,
        )
    except asyncio.CancelledError as exc:
        await asyncio.shield(_save_run_failure(database, user_id, run_id, exc, "cancelled"))
        raise
    except Exception as exc:
        await _save_run_failure(database, user_id, run_id, exc, "failed")
        raise
    serializable = {
        "run_id": run_id, "session_id": session_item.id, "status": state.get("status"),
        "final_answer": state.get("final_answer"), "verification": state.get("verification_result"),
        "tool_results": state.get("tool_results", []),
    }
    async with database.session() as session:
        sessions = SessionRepository(session, user_id)
        await sessions.add_message(session_item.id, "assistant", state.get("final_answer", ""))
        runs = AgentRunRepository(session, user_id)
        await runs.save_state(run_id, serializable, state.get("status", "completed"))
        for item in state.get("tool_results", []):
            await runs.add_tool_call(run_id, item)
    return serializable


@router.post("/chat")
async def chat(request: Request, body: ChatRequest, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    result = await _run(request, body, database, user_id)
    return {"success": True, "data": result, "meta": {}}


@router.post("/chat/stream")
async def chat_stream(request: Request, body: ChatRequest, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    def encode(event: str, payload: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def events():
        run_id = str(uuid.uuid4())
        queue: asyncio.Queue[tuple[str, dict[str, Any]]] = asyncio.Queue()

        async def on_event(event: str, payload: dict[str, Any]) -> None:
            await queue.put((event, {"run_id": run_id, **payload}))

        task = asyncio.create_task(
            _run(request, body, database, user_id, run_id=run_id, on_event=on_event)
        )
        yield encode("run_started", {"run_id": run_id, "message": "Agent 已开始执行"})
        try:
            while not task.done() or not queue.empty():
                try:
                    event, payload = await asyncio.wait_for(queue.get(), timeout=10)
                    yield encode(event, payload)
                except TimeoutError:
                    if await request.is_disconnected():
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                        return
                    yield encode(
                        "run_progress",
                        {"run_id": run_id, "stage": "waiting", "message": "仍在执行，请稍候…"},
                    )

            result = await task
            answer = result.get("final_answer") or ""
            for start in range(0, len(answer), 120):
                yield encode("answer_delta", {"run_id": run_id, "delta": answer[start:start + 120]})
            yield encode(
                "run_finished",
                {"run_id": run_id, "session_id": result["session_id"], "status": result["status"]},
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            yield encode(
                "error",
                {"run_id": run_id, "code": "AGENT_RUN_FAILED", "message": str(exc) or type(exc).__name__},
            )
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/agent/runs/{run_id}")
async def get_run(run_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await AgentRunRepository(session, user_id).get(run_id)
        if not item:
            raise HTTPException(404, "Agent run not found")
        return {"success": True, "data": {"id": item.id, "status": item.status, "state": item.state, "error": item.error}, "meta": {}}


@router.get("/agent/runs/{run_id}/tools")
async def get_run_tools(run_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        if not await AgentRunRepository(session, user_id).get(run_id):
            raise HTTPException(404, "Agent run not found")
        items = list((await session.scalars(select(ToolCallRecord).where(ToolCallRecord.run_id == run_id).order_by(ToolCallRecord.created_at))).all())
    data = [{"id": i.id, "tool": i.tool_name, "arguments": i.arguments, "result": i.result, "status": i.status, "duration_ms": i.duration_ms, "source": i.source, "error": i.error} for i in items]
    return {"success": True, "data": data, "meta": {"count": len(data)}}
