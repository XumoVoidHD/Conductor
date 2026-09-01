"""API v1 router aggregate."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth
from app.api.v1 import dashboard
from app.api.v1 import logs

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(logs.router)
