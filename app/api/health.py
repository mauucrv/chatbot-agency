"""
Health check endpoints.
"""

import structlog
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.services.redis_cache import redis_cache
import pytz

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])

TZ = pytz.timezone(settings.calendar_timezone)


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Basic health check endpoint.
    Returns 200 if the application is running.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": datetime.now(TZ).isoformat(),
        },
    )


@router.get("/health/ready")
async def readiness_check() -> JSONResponse:
    """
    Readiness check endpoint.
    Verifies database, Redis, and external service connectivity.
    """
    checks: Dict[str, Any] = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        checks["database"] = "unavailable"

    # Check Redis
    try:
        checks["redis"] = await redis_cache.ping()
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))
        checks["redis"] = "unavailable"

    # Check external services (non-blocking, logged but don't fail readiness)
    external_checks: Dict[str, Any] = {}

    # Check Chatwoot connectivity
    if settings.chatwoot_base_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.chatwoot_base_url.rstrip('/')}/auth/sign_in")
                external_checks["chatwoot"] = resp.status_code < 500
        except Exception as e:
            external_checks["chatwoot"] = "unreachable"

    # Determine overall status (only core services block readiness)
    all_healthy = all(v is True for v in checks.values())

    response_content = {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
        "timestamp": datetime.now(TZ).isoformat(),
    }
    if external_checks:
        response_content["external"] = external_checks

    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content=response_content,
    )


@router.get("/health/live")
async def liveness_check() -> JSONResponse:
    """
    Liveness check endpoint.
    Simple check that the application is responding.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "alive",
            "timestamp": datetime.now(TZ).isoformat(),
        },
    )
