"""Integration tests for admin statistics API."""

import pytest
from datetime import datetime, timezone


class TestStatsOverview:
    """GET /api/admin/estadisticas/overview"""

    async def test_requires_auth(self, app_client):
        resp = await app_client.get("/api/admin/estadisticas/overview", params={
            "fecha_desde": "2024-01-01T00:00:00Z",
            "fecha_hasta": "2024-12-31T23:59:59Z",
        })
        assert resp.status_code in (401, 403)

    async def test_returns_cached_data(self, admin_client, mock_redis):
        key = "admin:1:stats_overview:2024-01-01:2024-12-31"
        mock_redis._store[key] = {
            "daily_stats": [],
            "servicios_populares": [{"servicio": "Corte", "cantidad": 10}],
            "citas_por_estado": [{"estado": "completada", "cantidad": 8}],
            "citas_por_estilista": [{"estilista": "Ana", "cantidad": 5}],
            "tasa_completadas": 80.0,
            "tasa_canceladas": 10.0,
        }
        resp = await admin_client.get("/api/admin/estadisticas/overview", params={
            "fecha_desde": "2024-01-01T00:00:00Z",
            "fecha_hasta": "2024-12-31T23:59:59Z",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasa_completadas"] == 80.0


class TestAppointmentTrend:
    """GET /api/admin/estadisticas/tendencia-citas"""

    async def test_requires_auth(self, app_client):
        resp = await app_client.get("/api/admin/estadisticas/tendencia-citas")
        assert resp.status_code in (401, 403)

    async def test_returns_cached_trend(self, admin_client, mock_redis):
        mock_redis._store["admin:1:trend:30"] = [
            {"fecha": "2024-03-01T00:00:00", "valor": 5.0},
            {"fecha": "2024-03-02T00:00:00", "valor": 8.0},
        ]
        resp = await admin_client.get("/api/admin/estadisticas/tendencia-citas?dias=30")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
