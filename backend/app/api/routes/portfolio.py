from fastapi import APIRouter, Depends

from ..dependencies import get_current_user_id, get_database, get_services
from ...core.container import ServiceContainer
from ...db.repositories import PortfolioRepository
from ...db.session import Database
from ...schemas.portfolio import Portfolio

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def dump(record):
    return {"grams": record.grams, "average_cost": record.average_cost, "planned_investment": record.planned_investment, "currency": record.currency}


@router.get("")
async def get_portfolio(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        record = await PortfolioRepository(session, user_id).get_or_create()
        return {"success": True, "data": dump(record), "meta": {}}


@router.put("")
async def update_portfolio(body: Portfolio, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        record = await PortfolioRepository(session, user_id).get_or_create()
        record.grams, record.average_cost, record.planned_investment = body.grams, body.average_cost, body.planned_investment
        return {"success": True, "data": dump(record), "meta": {}}


@router.get("/analysis")
async def analyze_portfolio(
    current_price: float, database: Database = Depends(get_database),
    services: ServiceContainer = Depends(get_services), user_id: str = Depends(get_current_user_id),
):
    async with database.session() as session:
        record = await PortfolioRepository(session, user_id).get_or_create()
        body = Portfolio(grams=record.grams, average_cost=record.average_cost, planned_investment=record.planned_investment)
    result = services.portfolio.analyze(body, current_price)
    return {"success": True, "data": result.model_dump(mode="json"), "meta": {}}
