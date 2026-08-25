from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_current_user_id, get_database
from ...db.repositories import SessionRepository
from ...db.session import Database

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    title: str = Field(default="新会话", max_length=200)


class SessionPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def dump_session(item):
    return {"id": item.id, "title": item.title, "status": item.status, "created_at": item.created_at.isoformat(), "updated_at": item.updated_at.isoformat()}


@router.get("")
async def list_sessions(limit: int = 50, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = await SessionRepository(session, user_id).list(min(max(limit, 1), 100))
        return {"success": True, "data": [dump_session(item) for item in items], "meta": {"count": len(items)}}


@router.post("")
async def create_session(body: SessionCreate, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await SessionRepository(session, user_id).create(body.title)
        return {"success": True, "data": dump_session(item), "meta": {}}


@router.get("/{session_id}")
async def get_session(session_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await SessionRepository(session, user_id).get(session_id)
        if not item:
            raise HTTPException(404, "Session not found")
        return {"success": True, "data": dump_session(item), "meta": {}}


@router.patch("/{session_id}")
async def rename_session(session_id: str, body: SessionPatch, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await SessionRepository(session, user_id).rename(session_id, body.title)
        if not item:
            raise HTTPException(404, "Session not found")
        return {"success": True, "data": dump_session(item), "meta": {}}


@router.delete("/{session_id}")
async def delete_session(session_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        if not await SessionRepository(session, user_id).delete(session_id):
            raise HTTPException(404, "Session not found")
    return {"success": True, "data": {"deleted": True}, "meta": {}}


@router.get("/{session_id}/messages")
async def messages(session_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = await SessionRepository(session, user_id).messages(session_id)
    data = [{"id": item.id, "role": item.role, "content": item.content, "intent": item.intent, "created_at": item.created_at.isoformat()} for item in items]
    return {"success": True, "data": data, "meta": {"count": len(data)}}
