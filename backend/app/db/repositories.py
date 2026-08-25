"""Tenant-scoped repositories."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AgentRun, MessageRecord, PortfolioRecord, SessionRecord, ToolCallRecord, User


DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_demo_user(self) -> User:
        user = await self.session.get(User, DEMO_USER_ID)
        if user is None:
            user = User(id=DEMO_USER_ID, email="demo@goldagent.local", password_hash=None)
            self.session.add(user)
            await self.session.flush()
        return user


class SessionRepository:
    def __init__(self, session: AsyncSession, user_id: str):
        self.session, self.user_id = session, user_id

    async def create(self, title: str | None = None) -> SessionRecord:
        record = SessionRecord(user_id=self.user_id, title=title or "新会话")
        self.session.add(record)
        await self.session.flush()
        return record

    async def list(self, limit: int = 50) -> list[SessionRecord]:
        query = select(SessionRecord).where(SessionRecord.user_id == self.user_id).order_by(SessionRecord.updated_at.desc()).limit(limit)
        return list((await self.session.scalars(query)).all())

    async def get(self, session_id: str) -> SessionRecord | None:
        query = select(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == self.user_id)
        return await self.session.scalar(query)

    async def rename(self, session_id: str, title: str) -> SessionRecord | None:
        record = await self.get(session_id)
        if record:
            record.title = title[:200]
        return record

    async def delete(self, session_id: str) -> bool:
        result = await self.session.execute(delete(SessionRecord).where(SessionRecord.id == session_id, SessionRecord.user_id == self.user_id))
        return bool(result.rowcount)

    async def messages(self, session_id: str) -> list[MessageRecord]:
        if not await self.get(session_id):
            return []
        query = select(MessageRecord).where(MessageRecord.session_id == session_id).order_by(MessageRecord.created_at)
        return list((await self.session.scalars(query)).all())

    async def add_message(self, session_id: str, role: str, content: str, intent: str | None = None) -> MessageRecord:
        if not await self.get(session_id):
            raise ValueError("Session not found")
        record = MessageRecord(session_id=session_id, role=role, content=content, intent=intent, created_at=datetime.now(timezone.utc))
        self.session.add(record)
        await self.session.flush()
        return record


class PortfolioRepository:
    def __init__(self, session: AsyncSession, user_id: str):
        self.session, self.user_id = session, user_id

    async def get_or_create(self) -> PortfolioRecord:
        record = await self.session.scalar(select(PortfolioRecord).where(PortfolioRecord.user_id == self.user_id))
        if record is None:
            record = PortfolioRecord(user_id=self.user_id)
            self.session.add(record)
            await self.session.flush()
        return record


class AgentRunRepository:
    def __init__(self, session: AsyncSession, user_id: str):
        self.session, self.user_id = session, user_id

    async def create(self, session_id: str, run_id: str) -> AgentRun:
        run = AgentRun(id=run_id, user_id=self.user_id, session_id=session_id, status="running", state={})
        self.session.add(run)
        await self.session.flush()
        return run

    async def get(self, run_id: str) -> AgentRun | None:
        return await self.session.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == self.user_id))

    async def save_state(self, run_id: str, state: dict[str, Any], status: str) -> None:
        run = await self.get(run_id)
        if run:
            run.state, run.status = state, status

    async def save_failure(self, run_id: str, error: str, status: str = "failed") -> None:
        run = await self.get(run_id)
        if run:
            run.status = status
            run.error = error[:4000]

    async def add_tool_call(self, run_id: str, item: dict[str, Any]) -> ToolCallRecord:
        record = ToolCallRecord(
            run_id=run_id, tool_name=item["tool"], arguments=item.get("arguments", {}),
            result=item.get("output"), status="failed" if item.get("error") else "completed",
            duration_ms=item.get("duration_ms"),
            source=((item.get("output") or {}).get("metadata") or {}).get("source"),
            error=item.get("error"), created_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        await self.session.flush()
        return record
