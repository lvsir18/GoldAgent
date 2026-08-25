from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database, get_services
from ...core.container import ServiceContainer
from ...db.models import ReportRecord
from ...db.session import Database

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    report_type: str = "analysis"
    title: str = Field(min_length=1, max_length=255)
    payload: dict = Field(default_factory=dict)


def dump(item, content: bool = False):
    value = {"id": item.id, "report_type": item.report_type, "title": item.title, "metadata": item.metadata_json, "created_at": item.created_at.isoformat()}
    if content: value["content"] = item.content
    return value


@router.get("")
async def list_reports(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = list((await session.scalars(select(ReportRecord).where(ReportRecord.user_id == user_id).order_by(ReportRecord.created_at.desc()))).all())
    return {"success": True, "data": [dump(i) for i in items], "meta": {"count": len(items)}}


@router.post("")
async def create_report(body: ReportCreate, database: Database = Depends(get_database), services: ServiceContainer = Depends(get_services), user_id: str = Depends(get_current_user_id)):
    content = services.reports.render_markdown(body.report_type, body.title, body.payload)
    async with database.session() as session:
        item = ReportRecord(user_id=user_id, report_type=body.report_type, title=body.title, content=content, metadata_json=body.payload)
        session.add(item); await session.flush()
        return {"success": True, "data": dump(item, True), "meta": {}}


async def get_owned(report_id, database, user_id):
    async with database.session() as session:
        item = await session.get(ReportRecord, report_id)
        if not item or item.user_id != user_id: raise HTTPException(404, "Report not found")
        return item


@router.get("/{report_id}")
async def get_report(report_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    return {"success": True, "data": dump(await get_owned(report_id, database, user_id), True), "meta": {}}


@router.get("/{report_id}/download", response_class=PlainTextResponse)
async def download_report(report_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    return (await get_owned(report_id, database, user_id)).content


@router.delete("/{report_id}")
async def delete_report(report_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.get(ReportRecord, report_id)
        if not item or item.user_id != user_id: raise HTTPException(404, "Report not found")
        await session.delete(item)
    return {"success": True, "data": {"deleted": True}, "meta": {}}
