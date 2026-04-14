"""Integration tests for health check endpoints."""

import pytest
from unittest.mock import patch, AsyncMock


class TestHealth:
    """GET /health"""

    async def test_returns_healthy(self, app_client):
        resp = await app_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestLiveness:
    """GET /health/live"""

    async def test_returns_alive(self, app_client):
        resp = await app_client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"


class TestSecurityHeaders:
    """Verify security headers are present on responses."""

    async def test_has_x_frame_options(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    async def test_has_x_content_type_options(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    async def test_has_x_xss_protection(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("x-xss-protection") == "1; mode=block"

    async def test_has_referrer_policy(self, app_client):
        resp = await app_client.get("/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


class TestReadiness:
    """GET /health/ready"""

    async def test_ready_when_all_up(self, app_client, mock_redis):
        """When DB and Redis are healthy, should return ready."""
        resp = await app_client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["redis"] is True
