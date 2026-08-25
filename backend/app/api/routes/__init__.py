from fastapi import APIRouter

from .agent import router as agent_router
from .forecasts import router as forecasts_router
from .health import router as health_router
from .market import router as market_router
from .news import router as news_router
from .portfolio import router as portfolio_router
from .sessions import router as sessions_router
from .users import router as users_router
from .backtests import router as backtests_router
from .reports import router as reports_router
from .knowledge import router as knowledge_router
from .auth import router as auth_router

api_router = APIRouter()
for router in (auth_router, market_router, sessions_router, agent_router, forecasts_router, backtests_router, portfolio_router, news_router, reports_router, knowledge_router, users_router):
    api_router.include_router(router)

__all__ = ["api_router", "health_router"]
