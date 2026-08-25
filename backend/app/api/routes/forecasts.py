from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database, get_services
from ...core.container import ServiceContainer
from ...db.models import ForecastRecord
from ...db.session import Database
from ...schemas.forecast import ForecastRequest

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.post("")
async def create_forecast(
    body: ForecastRequest,
    services: ServiceContainer = Depends(get_services),
    database: Database = Depends(get_database),
    user_id: str = Depends(get_current_user_id),
):
    source = await services.market.history_frame(body.symbol, "CN", "3y")
    result = services.forecast.forecast(source.frame, source.metadata, body)
    result.metrics = services.forecast.evaluate(source.frame["close"].dropna().to_numpy(), body.model)
    payload = result.model_dump(mode="json")
    async with database.session() as session:
        session.add(ForecastRecord(id=result.id, user_id=user_id, request=body.model_dump(mode="json"), result=payload))
    return {"success": True, "data": payload, "meta": {}}


@router.get("")
async def list_forecasts(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        items = list((await session.scalars(select(ForecastRecord).where(ForecastRecord.user_id == user_id).order_by(ForecastRecord.created_at.desc()))).all())
    data = [{"id": item.id, "status": item.status, "request": item.request, "created_at": item.created_at.isoformat()} for item in items]
    return {"success": True, "data": data, "meta": {"count": len(data)}}


async def owned(forecast_id: str, database: Database, user_id: str) -> ForecastRecord:
    async with database.session() as session:
        item = await session.get(ForecastRecord, forecast_id)
        if not item or item.user_id != user_id:
            raise HTTPException(404, "Forecast not found")
        return item


@router.get("/{forecast_id}")
async def get_forecast(forecast_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    return {"success": True, "data": (await owned(forecast_id, database, user_id)).result, "meta": {}}


@router.get("/{forecast_id}/evaluation")
async def forecast_evaluation(forecast_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    return {"success": True, "data": (await owned(forecast_id, database, user_id)).result["metrics"], "meta": {}}


@router.delete("/{forecast_id}")
async def delete_forecast(forecast_id: str, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.get(ForecastRecord, forecast_id)
        if not item or item.user_id != user_id:
            raise HTTPException(404, "Forecast not found")
        await session.delete(item)
    return {"success": True, "data": {"deleted": True}, "meta": {}}
