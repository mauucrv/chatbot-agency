"""
Main FastAPI application for the AgencyBot Chatbot.
"""

import os
import traceback

import structlog
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import close_db, init_db
from app.api import admin_router, health_router, webhooks_router
from app.jobs import init_scheduler, shutdown_scheduler
from app.services.redis_cache import redis_cache
from app.services.telegram_notifier import notify_error
from app.utils.logging import setup_logging, strip_sensitive_params
from app.utils.seed_data import seed_initial_data

# Setup logging first
setup_logging()

logger = structlog.get_logger(__name__)


async def _run_migrations() -> None:
    """Run alembic migrations on startup."""
    try:
        from alembic.config import Config
        from alembic import command
        from sqlalchemy import text as sa_text
        from app.database import get_session_context

        # Ensure alembic_version.version_num can hold our revision IDs
        async with get_session_context() as session:
            await session.execute(sa_text(
                "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"
            ))

        alembic_cfg = Config("alembic.ini")
        # Run upgrade in a thread to avoid blocking the event loop
        import asyncio
        await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
        logger.info("Database migrations completed")
    except Exception as e:
        logger.warning("Could not run alembic migrations (tables will be created directly)", error=str(e))


def _validate_password_complexity(password: str) -> bool:
    """Check password has min 12 chars, uppercase, lowercase, digit, and special char."""
    import re
    if len(password) < 12:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[^A-Za-z0-9]", password):
        return False
    return True


async def _seed_admin_user() -> None:
    """Create or sync the admin user from ADMIN_USERNAME / ADMIN_PASSWORD env vars."""
    if not settings.admin_password:
        return
    if settings.is_production and not _validate_password_complexity(settings.admin_password):
        logger.error(
            "ADMIN_PASSWORD does not meet complexity requirements "
            "(min 12 chars, uppercase, lowercase, digit, special char). "
            "Skipping admin user seed."
        )
        return
    try:
        from sqlalchemy import select, func
        from app.database import get_session_context
        from app.models.models import AdminUser, RolAdmin
        from app.services.admin_auth_service import hash_password, verify_password

        async with get_session_context() as session:
            result = await session.execute(
                select(AdminUser).where(AdminUser.username == settings.admin_username)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = AdminUser(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    rol=RolAdmin.ADMIN,
                )
                session.add(user)
                logger.info("Admin user created", username=settings.admin_username)
            elif not verify_password(settings.admin_password, user.password_hash):
                user.password_hash = hash_password(settings.admin_password)
                logger.info("Admin user password synced from env", username=settings.admin_username)
    except Exception as e:
        logger.warning("Could not seed admin user", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database, Redis, scheduler, and seed data
    - Shutdown: Clean up resources
    """
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app_name,
        environment=settings.app_env,
    )

    try:
        # Run migrations first, then initialize database
        await _run_migrations()

        logger.info("Initializing database...")
        await init_db()
        logger.info("Database initialized")

        # Test Redis connection
        logger.info("Testing Redis connection...")
        redis_ok = await redis_cache.ping()
        if redis_ok:
            logger.info("Redis connection successful")
        else:
            logger.warning("Redis connection failed - caching will be disabled")

        # Seed initial data
        await seed_initial_data()

        # Seed admin user if ADMIN_PASSWORD is set and table is empty
        await _seed_admin_user()

        # Initialize scheduler
        logger.info("Initializing scheduler...")
        init_scheduler()
        logger.info("Scheduler initialized")

        # Run calendar sync immediately on startup to verify Google credentials
        try:
            from app.jobs.sync_calendar import sync_calendar_events
            await sync_calendar_events()
            logger.info("Initial calendar sync completed")
        except Exception as e:
            logger.error("Initial calendar sync failed", error=str(e))

        logger.info(
            "Application started successfully",
            port=settings.port,
        )

        yield

    except Exception as e:
        logger.error("Failed to start application", error=str(e))
        try:
            await notify_error(
                "unhandled_exception",
                f"Application failed to start: {str(e)}",
                traceback_str=traceback.format_exc(),
            )
        except Exception:
            pass
        raise

    finally:
        # Shutdown
        logger.info("Shutting down application...")

        # Shutdown scheduler
        shutdown_scheduler()

        # Close Redis connection
        await redis_cache.close()

        # Close database connections
        await close_db()

        logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=f"{settings.salon_name} - Chatbot API",
    description=f"WhatsApp chatbot for {settings.business_type} appointment management.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
if settings.allowed_origins:
    allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
else:
    allowed_origins = ["*"] if not settings.is_production else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if "*" not in allowed_origins else False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # CSP: prevent inline scripts from stealing localStorage tokens
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    return response

# Include routers
app.include_router(health_router)
app.include_router(webhooks_router, prefix="/api")
app.include_router(admin_router)

# Serve admin SPA static files
_admin_dist = os.path.join(os.path.dirname(__file__), "..", "admin", "dist")
if os.path.isdir(_admin_dist):
    app.mount("/admin/assets", StaticFiles(directory=os.path.join(_admin_dist, "assets")), name="admin-assets")

    _admin_dist_real = os.path.realpath(_admin_dist)

    @app.get("/admin/{full_path:path}")
    async def serve_admin_spa(full_path: str = ""):
        # Serve static files (logos, etc.) if they exist in dist root
        if full_path:
            file_path = os.path.realpath(os.path.join(_admin_dist, full_path))
            # Prevent path traversal — file must be inside admin dist directory
            if not file_path.startswith(_admin_dist_real + os.sep):
                raise HTTPException(status_code=404, detail="Not found")
            if os.path.isfile(file_path):
                return FileResponse(file_path)
        return FileResponse(os.path.join(_admin_dist, "index.html"))
else:
    @app.get("/admin/{full_path:path}")
    async def admin_not_built(full_path: str = ""):
        return JSONResponse(
            status_code=404,
            content={"detail": "Admin panel not built. Run 'npm run build' in admin/."},
        )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if settings.is_production:
        return JSONResponse(status_code=422, content={"detail": "Datos de entrada inválidos"})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions and send Telegram alert."""
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(
        "Unhandled exception",
        path=strip_sensitive_params(str(request.url)),
        method=request.method,
        error=str(exc),
    )
    await notify_error(
        error_type="unhandled_exception",
        message=f"{request.method} {request.url.path}: {str(exc)[:300]}",
        traceback_str=tb_str,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
