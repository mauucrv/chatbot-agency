"""Integration tests for admin dashboard API."""

import pytest


class TestDashboard:
    """GET /api/admin/dashboard"""

    async def test_requires_auth(self, app_client):
        resp = await app_client.get("/api/admin/dashboard")
        assert resp.status_code in (401, 403)

    async def test_returns_cached_metrics(self, admin_client, mock_redis):
        """Pre-populate cache and verify the endpoint returns it."""
        mock_redis._store["admin:1:dashboard"] = {
            "citas_hoy": 5,
            "citas_pendientes": 3,
            "citas_completadas_hoy": 2,
            "ingresos_hoy": 750.0,
            "total_servicios": 10,
            "total_estilistas": 4,
            "mensajes_hoy": 50,
            "errores_hoy": 1,
            "total_leads": 15,
            "leads_nuevos_hoy": 2,
            "leads_en_pipeline": 8,
            "seguimientos_pendientes": 3,
            "uso": {
                "mensajes_mes": 500,
                "mensajes_audio_mes": 20,
                "mensajes_imagen_mes": 10,
                "tokens_openai_mes": 100000,
                "usuarios_unicos_hoy": 12,
            },
            "citas_semana": [],
            "citas_recientes": [],
        }
        resp = await admin_client.get("/api/admin/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["citas_hoy"] == 5
        assert data["ingresos_hoy"] == 750.0

    async def test_viewer_can_access(self, viewer_client, mock_redis):
        """Viewers should also have read access to dashboard."""
        mock_redis._store["admin:1:dashboard"] = {
            "citas_hoy": 0,
            "citas_pendientes": 0,
            "citas_completadas_hoy": 0,
            "ingresos_hoy": 0.0,
            "total_servicios": 0,
            "total_estilistas": 0,
            "mensajes_hoy": 0,
            "errores_hoy": 0,
            "total_leads": 0,
            "leads_nuevos_hoy": 0,
            "leads_en_pipeline": 0,
            "seguimientos_pendientes": 0,
            "uso": {
                "mensajes_mes": 0,
                "mensajes_audio_mes": 0,
                "mensajes_imagen_mes": 0,
                "tokens_openai_mes": 0,
                "usuarios_unicos_hoy": 0,
            },
            "citas_semana": [],
            "citas_recientes": [],
        }
        resp = await viewer_client.get("/api/admin/dashboard")
        assert resp.status_code == 200
