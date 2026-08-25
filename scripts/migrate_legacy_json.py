"""Idempotent importer for legacy chat JSON into the GoldAgent database."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.db.repositories import DEMO_USER_ID, SessionRepository, UserRepository
from backend.app.db.session import build_database
from src.settings import AppSettings


async def migrate(root: Path) -> dict[str, int]:
    settings = AppSettings.load(root / "config.yaml")
    database = build_database(settings)
    await database.create_all()
    imported_sessions = imported_messages = 0
    async with database.session() as db:
        await UserRepository(db).ensure_demo_user()
        repository = SessionRepository(db, DEMO_USER_ID)
        for path in sorted((root / "data/chat_sessions").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            session_id = payload.get("session_id") or path.stem
            if await repository.get(session_id):
                continue
            from backend.app.db.models import SessionRecord
            record = SessionRecord(id=session_id, user_id=DEMO_USER_ID, title=payload.get("title") or "迁移会话")
            db.add(record)
            await db.flush()
            imported_sessions += 1
            for item in payload.get("messages", []):
                created = item.get("timestamp")
                try:
                    created_at = datetime.fromisoformat(created) if created else datetime.now(timezone.utc)
                except ValueError:
                    created_at = datetime.now(timezone.utc)
                from backend.app.db.models import MessageRecord
                db.add(MessageRecord(
                    session_id=session_id, role=item.get("role", "user"), content=item.get("content", ""),
                    intent=item.get("intent"), created_at=created_at,
                ))
                imported_messages += 1
    await database.dispose()
    return {"sessions": imported_sessions, "messages": imported_messages}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    print(asyncio.run(migrate(parser.parse_args().root)))
