"""
Shared test fixtures for the AgencyBot bot test suite.

Sets up:
- SQLite async test database (no PostgreSQL needed)
- Redis mock (no Redis server needed)
- Authenticated httpx clients for integration tests
- External service mocks
"""

import os

# Set test env vars BEFORE any app imports
os.environ.update({
    "APP_ENV": "development",
    # Use fake postgres URL so app.database's module-level engine creation
    # succeeds with pool_size/max_overflow (SQLite rejects those params).
    # We override the engine immediately after import anyway.
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/testdb",  # pragma: allowlist secret
    "REDIS_URL": "",
    "SECRET_KEY": "test-secret-key-for-testing-only",  # pragma: allowlist secret
    "OPENAI_API_KEY": "test-key",  # pragma: allowlist secret
    "CHATWOOT_BASE_URL": "http://test-chatwoot",
    "CHATWOOT_API_TOKEN": "test-token",
    "CHATWOOT_WEBHOOK_TOKEN": "test-webhook-token",
    "GOOGLE_CALENDAR_ID": "test-calendar@group.calendar.google.com",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "TestAdmin1Pass!",  # pragma: allowlist secret
    "SALON_NAME": "Test Salon",
})

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.database as db_module
from app.database import Base
from app.models.models import AdminUser, RolAdmin, Tenant, PlanTenant
from app.services.admin_auth_service import create_access_token, hash_password


# ── Test Database Engine ──────────────────────────────────────

test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
test_session_maker = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def test_get_session_context():
    """Test override for get_session_context."""
    async with test_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Patch the database module BEFORE the app is imported
db_module.engine = test_engine
db_module.async_session_maker = test_session_maker
db_module.get_session_context = test_get_session_context


# ── Database Fixtures ─────────────────────────────────────────


@pytest.fixture(autouse=True)
async def db_tables():
    """Create and drop all tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    """Provide a test database session."""
    async with test_session_maker() as session:
        yield session


# ── Redis Mock ────────────────────────────────────────────────


class FakeRedisCache:
    """In-memory fake Redis cache for testing."""

    def __init__(self):
        self._store = {}

    async def ping(self):
        return True

    async def close(self):
        self._store.clear()

    async def get(self, key):
        return self._store.get(key)

    async def set(self, key, value, ex=None):
        self._store[key] = value

    async def delete(self, key):
        self._store.pop(key, None)

    async def invalidate_services(self, tenant_id=1):
        pass

    async def invalidate_stylists(self, tenant_id=1):
        pass

    async def invalidate_info(self, tenant_id=1):
        pass

    async def invalidate_keywords(self, tenant_id=1):
        pass

    async def invalidate_fichas(self, tenant_id=1):
        pass

    async def invalidate_inventario(self, tenant_id=1):
        pass

    async def invalidate_ventas(self, tenant_id=1):
        pass

    async def invalidate_informes(self, tenant_id=1):
        pass

    async def get_services(self, tenant_id=1):
        return None

    async def set_services(self, tenant_id, data, ttl=300):
        pass

    async def get_stylists(self, tenant_id=1):
        return None

    async def set_stylists(self, tenant_id, data, ttl=300):
        pass

    async def get_info(self, tenant_id=1):
        return None

    async def set_info(self, tenant_id, data, ttl=300):
        pass

    async def get_keywords(self, tenant_id=1):
        return None

    async def set_keywords(self, tenant_id, data, ttl=300):
        pass

    async def check_rate_limit(self, tenant_id, phone, max_msg, window):
        return True, 0

    async def check_login_rate_limit(self, ip):
        return True, 0

    async def clear_login_attempts(self, ip):
        pass

    async def get_admin_cache(self, tenant_id, key):
        val = self._store.get(f"admin:{tenant_id}:{key}")
        return val

    async def set_admin_cache(self, tenant_id, key, value, ttl=60):
        self._store[f"admin:{tenant_id}:{key}"] = value

    async def invalidate_admin_cache_pattern(self, tenant_id, pattern):
        pass

    async def acquire_booking_lock(self, tenant_id, slot_key, ttl=30):
        k = f"{tenant_id}:{slot_key}"
        if k in self._store:
            return False
        self._store[k] = "locked"
        return True

    async def release_booking_lock(self, tenant_id, slot_key):
        self._store.pop(f"{tenant_id}:{slot_key}", None)
        return True

    async def get_pending_messages(self, tenant_id, conv_id):
        return []

    async def clear_pending_messages(self, tenant_id, conv_id):
        pass

    async def add_pending_message(self, tenant_id, conv_id, message):
        pass

    async def set_processing_lock(self, tenant_id, conv_id, ttl=30):
        return True

    async def release_processing_lock(self, tenant_id, conv_id):
        pass

    async def get_conversation_context(self, tenant_id, conv_id):
        return None

    async def set_conversation_context(self, tenant_id, conv_id, context, ttl=3600):
        pass

    async def clear_conversation_context(self, tenant_id, conv_id):
        pass

    async def should_send_paused_reply(self, tenant_id, conv_id, cooldown=300):
        return True

    async def clear_paused_reply_cooldown(self, tenant_id, conv_id):
        pass

    async def mark_rate_limit_owner_notified(self, tenant_id, phone, ttl=3600):
        return True

    async def get_rate_limit_remaining(self, tenant_id, phone, max_msg, window):
        return max_msg

    async def blacklist_token(self, jti, ttl_seconds):
        self._store[f"blacklist:{jti}"] = "1"
        return True

    async def is_token_blacklisted(self, jti):
        return f"blacklist:{jti}" in self._store

    async def invalidate_user_tokens(self, username):
        import time
        self._store[f"user_invalidated:{username}"] = str(time.time())
        return True

    async def get_user_tokens_invalidated_at(self, username):
        val = self._store.get(f"user_invalidated:{username}")
        return float(val) if val else None

    async def check_refresh_rate_limit(self, ip, max_attempts=20, window_seconds=900):
        return True, 0


@pytest.fixture(autouse=True)
def mock_redis():
    """Replace the global redis_cache singleton with a fake."""
    fake = FakeRedisCache()
    with patch("app.services.redis_cache.redis_cache", fake):
        # Also patch in modules that import redis_cache directly
        with patch("app.api.admin_auth.redis_cache", fake), \
             patch("app.api.admin_servicios.redis_cache", fake), \
             patch("app.api.admin_estilistas.redis_cache", fake), \
             patch("app.api.admin_info.redis_cache", fake), \
             patch("app.api.admin_dashboard.redis_cache", fake), \
             patch("app.api.admin_estadisticas.redis_cache", fake), \
             patch("app.api.health.redis_cache", fake), \
             patch("app.utils.admin_deps.redis_cache", fake):
            yield fake


# ── Telegram Mock ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_telegram():
    """Prevent Telegram notifications during tests."""
    with patch("app.services.telegram_notifier.telegram_notifier") as mock:
        mock.send_alert = AsyncMock(return_value=False)
        yield mock


# ── App Client Fixtures ───────────────────────────────────────


@pytest.fixture
async def app_client():
    """httpx AsyncClient bound to the FastAPI app (no auth)."""
    import httpx
    from app.main import app

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
async def test_tenant(db_session: AsyncSession):
    """Create the default test tenant."""
    tenant = Tenant(
        id=1,
        nombre="Test Salon",
        slug="test-salon",
        plan=PlanTenant.ACTIVE,
        activo=True,
        timezone="America/Mexico_City",
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture
async def admin_user(db_session: AsyncSession, test_tenant):
    """Create an admin user in the test DB."""
    user = AdminUser(
        username="testadmin",
        password_hash=hash_password("testpass123"),
        rol=RolAdmin.ADMIN,
        activo=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def viewer_user(db_session: AsyncSession, test_tenant):
    """Create a viewer user in the test DB."""
    user = AdminUser(
        username="testviewer",
        password_hash=hash_password("viewerpass123"),
        rol=RolAdmin.VIEWER,
        activo=True,
        tenant_id=test_tenant.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user: AdminUser) -> str:
    """JWT access token for the admin user."""
    return create_access_token(admin_user.username, tenant_id=admin_user.tenant_id)


@pytest.fixture
def viewer_token(viewer_user: AdminUser) -> str:
    """JWT access token for the viewer user."""
    return create_access_token(viewer_user.username, tenant_id=viewer_user.tenant_id)


@pytest.fixture
async def admin_client(app_client, admin_token: str):
    """httpx client with admin Authorization header."""
    app_client.headers["Authorization"] = f"Bearer {admin_token}"
    return app_client


@pytest.fixture
async def viewer_client(admin_token: str, viewer_user):
    """httpx client with viewer Authorization header."""
    import httpx
    from app.main import app

    token = create_access_token(viewer_user.username)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client
