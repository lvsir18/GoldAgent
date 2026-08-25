"""FastAPI dependencies with demo-mode identity isolation."""

from fastapi import Depends, Request

from ..core.container import ServiceContainer
from ..db.repositories import DEMO_USER_ID
from ..db.session import Database


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_current_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return user_id
    if request.app.state.settings.security.demo_mode:
        return DEMO_USER_ID
    if not user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


CurrentUserId = Depends(get_current_user_id)
