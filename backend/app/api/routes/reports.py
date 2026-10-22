from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database, get_services
from ...core.container import ServiceContainer
from ...db.models import AgentRun, ReportRecord
from ...db.session import Database
from ...services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportCreate(BaseModel):
    report_type: str = "analysis"
    title: str = Field(min_length=1, max_length=255)
    payload: dict = Field(default_factory=dict)
    run_id: str | None = None


def dump(item, content: bool = False):
    value = {"id": item.id, "report_type": item.report_type, "title": item.title, "metadata": item.metadata_json, "created_at": item.created_at.isoformat()}
    if content: value["content"] = public_content(item)
    return value


def public_content(item):
    # Render legacy reports from stored facts too; do not mutate history.
    return ReportService().render_markdown(item.report_type, item.title, item.metadata_json or {}, item.created_at)


@router.get("")
async def list_reports(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = list((await session.scalars(select(ReportRecord).where(ReportRecord.user_id == user_id).order_by(ReportRecord.created_at.desc()))).all())
    return {"success": True, "data": [dump(i) for i in items], "meta": {"count": len(items)}}


@router.post("")
async def create_report(body: ReportCreate, database: Database = Depends(get_database), services: ServiceContainer = Depends(get_services), user_id: str = Depends(get_current_user_id)):
    payload = dict(body.payload)
    if body.run_id:
        async with database.session() as session:
            run = await session.get(AgentRun, body.run_id)
            if not run or run.user_id != user_id:
                raise HTTPException(404, "Agent run not found")
            if run.status != "completed":
                raise HTTPException(409, "Only completed research can be saved as a report")
            payload = {"run_id": run.id, "session_id": run.session_id, **run.state}
    elif not payload:
        snapshot = await services.market.summary()
        payload = {"market_snapshot": snapshot.model_dump(mode="json"), "method": "Deterministic market snapshot; not an AI research report."}
    content = services.reports.render_markdown(body.report_type, body.title, payload)
    async with database.session() as session:
        item = ReportRecord(user_id=user_id, report_type=body.report_type, title=body.title, content=content, metadata_json=payload)
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
    return public_content(await get_owned(report_id, database, user_id))


@router.delete("/{report_id}")
async def delete_report(report_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.get(ReportRecord, report_id)
        if not item or item.user_id != user_id: raise HTTPException(404, "Report not found")
        await session.delete(item)
    return {"success": True, "data": {"deleted": True}, "meta": {}}
