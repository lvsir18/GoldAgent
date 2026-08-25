from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database, get_services
from ...core.container import ServiceContainer
from ...db.models import BacktestRecord
from ...db.session import Database
from ...schemas.backtest import BacktestRequest

router = APIRouter(prefix="/backtests", tags=["backtests"])


async def execute_backtest(record_id: str, user_id: str, database: Database, services: ServiceContainer):
    async with database.session() as session:
        record = await session.get(BacktestRecord, record_id)
        if not record or record.user_id != user_id:
            return
        record.status = "running"
        request = BacktestRequest.model_validate(record.request)
    try:
        source = await services.market.history_frame("AU0", "CN", "3y")
        result = services.backtest.run(source.frame, request)
        async with database.session() as session:
            record = await session.get(BacktestRecord, record_id)
            record.status, record.result = "completed", result.model_dump(mode="json")
    except Exception as exc:
        async with database.session() as session:
            record = await session.get(BacktestRecord, record_id)
            record.status, record.error = "failed", f"{type(exc).__name__}: {exc}"


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_backtest(
    body: BacktestRequest, tasks: BackgroundTasks, database: Database = Depends(get_database),
    services: ServiceContainer = Depends(get_services), user_id: str = Depends(get_current_user_id),
):
    async with database.session() as session:
        record = BacktestRecord(user_id=user_id, status="queued", request=body.model_dump(mode="json"))
        session.add(record); await session.flush(); record_id = record.id
    tasks.add_task(execute_backtest, record_id, user_id, database, services)
    return {"success": True, "data": {"id": record_id, "status": "queued"}, "meta": {}}


@router.get("")
async def list_backtests(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = list((await session.scalars(select(BacktestRecord).where(BacktestRecord.user_id == user_id).order_by(BacktestRecord.created_at.desc()))).all())
    return {"success": True, "data": [{"id": i.id, "status": i.status, "request": i.request, "created_at": i.created_at.isoformat()} for i in items], "meta": {"count": len(items)}}


async def owned(record_id: str, database: Database, user_id: str):
    async with database.session() as session:
        item = await session.get(BacktestRecord, record_id)
        if not item or item.user_id != user_id: raise HTTPException(404, "Backtest not found")
        return {"id": item.id, "status": item.status, "request": item.request, "result": item.result, "error": item.error, "created_at": item.created_at.isoformat()}


@router.get("/{backtest_id}")
async def get_backtest(backtest_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    return {"success": True, "data": await owned(backtest_id, database, user_id), "meta": {}}


@router.get("/{backtest_id}/trades")
async def get_trades(backtest_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    item = await owned(backtest_id, database, user_id)
    return {"success": True, "data": (item.get("result") or {}).get("trades", []), "meta": {}}


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.get(BacktestRecord, backtest_id)
        if not item or item.user_id != user_id: raise HTTPException(404, "Backtest not found")
        await session.delete(item)
    return {"success": True, "data": {"deleted": True}, "meta": {}}
