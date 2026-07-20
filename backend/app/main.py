"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import get_logger
from app.core.logging import setup_logging

setup_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "Starting %s (env=%s)",
        settings.app_name,
        settings.environment,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
    except SQLAlchemyError:
        logger.exception("Database connection failed at startup")
        raise
    yield
    logger.info("Shutting down %s", settings.app_name)
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Conductor platform API — authentication and future control plane.",
    version="0.1.0",
    lifespan=lifespan,
)

# Browser frontends (dev). Comma-separated origins via CORS_ORIGINS env.
_cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error."},
    )


@app.get("/health", tags=["health"], summary="Health check")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
