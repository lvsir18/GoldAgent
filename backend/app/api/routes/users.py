from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..dependencies import get_current_user_id, get_database
from ...db.models import RiskProfile, User, UserProfile
from ...db.session import Database

router = APIRouter(prefix="/users/me", tags=["users"])


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=100)
    preferences: dict = Field(default_factory=dict)


class RiskUpdate(BaseModel):
    risk_level: str = "balanced"
    max_drawdown_pct: float | None = Field(default=None, ge=0, le=100)
    horizon: str = "medium"
    notes: str = Field(default="", max_length=2000)


@router.get("")
async def me(database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        user = await session.get(User, user_id)
        profile = await session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        risk = await session.scalar(select(RiskProfile).where(RiskProfile.user_id == user_id))
    return {"success": True, "data": {"id": user.id, "email": user.email, "profile": {"display_name": profile.display_name, "preferences": profile.preferences} if profile else None, "risk_profile": {"risk_level": risk.risk_level, "max_drawdown_pct": risk.max_drawdown_pct, "horizon": risk.horizon, "notes": risk.notes} if risk else None}, "meta": {}}


@router.put("/profile")
async def update_profile(body: ProfileUpdate, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        if not item:
            item = UserProfile(user_id=user_id)
            session.add(item)
        item.display_name, item.preferences = body.display_name, body.preferences
        await session.flush()
        return {"success": True, "data": {"display_name": item.display_name, "preferences": item.preferences}, "meta": {}}


@router.put("/risk-profile")
async def update_risk(body: RiskUpdate, database: Database = Depends(get_database), user_id: str = Depends(get_current_user_id)):
    async with database.session() as session:
        item = await session.scalar(select(RiskProfile).where(RiskProfile.user_id == user_id))
        if not item:
            item = RiskProfile(user_id=user_id)
            session.add(item)
        item.risk_level, item.max_drawdown_pct, item.horizon, item.notes = body.risk_level, body.max_drawdown_pct, body.horizon, body.notes
        await session.flush()
        return {"success": True, "data": body.model_dump(), "meta": {}}
