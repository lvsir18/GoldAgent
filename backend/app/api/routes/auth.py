from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from ..dependencies import get_database
from ...core.security import TokenService, hash_password, verify_password
from ...db.models import RefreshToken, User
from ...db.session import Database

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class RefreshRequest(BaseModel): refresh_token: str


async def tokens(request: Request, database: Database, user: User):
    service=TokenService(request.app.state.settings.security); refresh=service.refresh_token()
    expires=datetime.now(timezone.utc)+timedelta(days=request.app.state.settings.security.refresh_token_days)
    async with database.session() as session:
        session.add(RefreshToken(user_id=user.id,token_hash=service.token_hash(refresh),expires_at=expires,created_at=datetime.now(timezone.utc)))
    return {"access_token":service.access_token(user.id),"refresh_token":refresh,"token_type":"bearer","expires_in":request.app.state.settings.security.access_token_minutes*60}


@router.post("/register")
async def register(request: Request, body: Credentials, database: Database = Depends(get_database)):
    async with database.session() as session:
        if await session.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,"Email already registered")
        user=User(email=body.email.lower(),password_hash=hash_password(body.password));session.add(user);await session.flush();user_id=user.id
    async with database.session() as session: user=await session.get(User,user_id)
    return {"success":True,"data":await tokens(request,database,user),"meta":{}}


@router.post("/login")
async def login(request: Request, body: Credentials, database: Database = Depends(get_database)):
    async with database.session() as session: user=await session.scalar(select(User).where(User.email==body.email.lower()))
    if not user or not user.password_hash or not verify_password(body.password,user.password_hash): raise HTTPException(401,"Invalid credentials")
    return {"success":True,"data":await tokens(request,database,user),"meta":{}}


@router.post("/refresh")
async def refresh(request: Request, body: RefreshRequest, database: Database = Depends(get_database)):
    service=TokenService(request.app.state.settings.security);token_hash=service.token_hash(body.refresh_token)
    async with database.session() as session:
        record=await session.scalar(select(RefreshToken).where(RefreshToken.token_hash==token_hash,RefreshToken.revoked.is_(False)))
        if not record or record.expires_at.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc): raise HTTPException(401,"Invalid refresh token")
        record.revoked=True;user=await session.get(User,record.user_id)
    return {"success":True,"data":await tokens(request,database,user),"meta":{}}


@router.post("/logout")
async def logout(request: Request, body: RefreshRequest, database: Database = Depends(get_database)):
    token_hash=TokenService(request.app.state.settings.security).token_hash(body.refresh_token)
    async with database.session() as session:
        record=await session.scalar(select(RefreshToken).where(RefreshToken.token_hash==token_hash));
        if record: record.revoked=True
    return {"success":True,"data":{"revoked":True},"meta":{}}
