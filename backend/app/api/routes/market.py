from fastapi import APIRouter, Depends, Query

from ..dependencies import get_services
from ...core.container import ServiceContainer

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/summary")
async def summary(symbol: str = "AU0", market: str = "CN", period: str = "3y", services: ServiceContainer = Depends(get_services)):
    data = await services.market.summary(symbol, market, period)
    return {"success": True, "data": data.model_dump(mode="json"), "meta": {}}


@router.get("/history")
async def history(
    symbol: str = "AU0", market: str = "CN", period: str = "3y",
    limit: int = Query(default=500, ge=5, le=5000), services: ServiceContainer = Depends(get_services),
):
    data = await services.market.history(symbol, market, period, limit)
    return {"success": True, "data": data.model_dump(mode="json"), "meta": {"count": len(data.points)}}


@router.get("/indicators")
async def indicators(symbol: str = "AU0", market: str = "CN", period: str = "3y", services: ServiceContainer = Depends(get_services)):
    source = await services.market.history_frame(symbol, market, period)
    _, snapshot = services.technical.calculate(source.frame, source.metadata)
    return {"success": True, "data": snapshot.model_dump(mode="json"), "meta": {}}


@router.get("/support-resistance")
async def support_resistance(symbol: str = "AU0", market: str = "CN", period: str = "3y", services: ServiceContainer = Depends(get_services)):
    source = await services.market.history_frame(symbol, market, period)
    _, snapshot = services.technical.calculate(source.frame, source.metadata)
    return {"success": True, "data": {"support": snapshot.support, "resistance": snapshot.resistance, "metadata": snapshot.metadata.model_dump(mode="json")}, "meta": {}}


@router.post("/refresh")
async def refresh():
    # Provider cache is introduced without pretending a refresh occurred.
    return {"success": True, "data": {"status": "not_supported"}, "meta": {"cache_invalidated": False}}
