from fastapi import APIRouter, Depends

from ..dependencies import get_services
from ...core.container import ServiceContainer

router = APIRouter(prefix="/news", tags=["news"])


@router.get("")
async def news(query: str = "黄金 美联储 美元", max_results: int = 10, services: ServiceContainer = Depends(get_services)):
    result = await services.news.search(query, max_results)
    return {"success": True, "data": result.model_dump(mode="json"), "meta": {"count": len(result.articles)}}


@router.post("/refresh")
async def refresh_news(query: str = "黄金 美联储 美元", services: ServiceContainer = Depends(get_services)):
    result = await services.news.search(query, 10)
    return {"success": True, "data": result.model_dump(mode="json"), "meta": {"refreshed": True}}
