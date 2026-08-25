"""Async database lifecycle."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.settings import AppSettings

from .base import Base
from . import models  # noqa: F401 - registers metadata


def async_database_url(url: str) -> str:
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


@dataclass(slots=True)
class Database:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    @asynccontextmanager
    async def session(self):
        async with self.sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_all(self) -> None:
        async with self.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await connection.run_sync(Base.metadata.create_all)

    async def recover_interrupted_agent_runs(self) -> int:
        """Close runs left active by a previous process crash or restart."""
        async with self.session() as session:
            result = await session.execute(
                update(models.AgentRun)
                .where(models.AgentRun.status == "running")
                .values(status="failed", error="Backend restarted before the Agent run completed")
            )
            return int(result.rowcount or 0)

    async def dispose(self) -> None:
        await self.engine.dispose()


def build_database(settings: AppSettings) -> Database:
    engine = create_async_engine(async_database_url(settings.database.url), echo=settings.database.echo, pool_pre_ping=True)
    return Database(engine=engine, sessions=async_sessionmaker(engine, expire_on_commit=False))
