"""Checkpoint selection for demo and production modes."""

from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import MemorySaver

from src.settings import AppSettings


@asynccontextmanager
async def checkpointer_context(settings: AppSettings):
    """Own the saver lifecycle and initialize PostgreSQL checkpoint tables."""
    if settings.database.url.startswith("postgresql"):
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as exc:
            if not settings.security.demo_mode:
                raise RuntimeError("Install langgraph-checkpoint-postgres for persistent checkpoints") from exc
        else:
            connection_url = settings.database.url.replace("postgresql+psycopg://", "postgresql://", 1)
            async with AsyncPostgresSaver.from_conn_string(connection_url) as saver:
                await saver.setup()
                yield saver
                return
    if not settings.security.demo_mode:
        raise RuntimeError("Persistent PostgreSQL checkpointing is required outside DEMO_MODE")
    yield MemorySaver()


def build_checkpointer(settings: AppSettings):
    """Compatibility helper for non-production, non-lifespan callers."""
    if not settings.security.demo_mode or settings.database.url.startswith("postgresql"):
        raise RuntimeError("Production checkpointers must be created through checkpointer_context")
    return MemorySaver()
