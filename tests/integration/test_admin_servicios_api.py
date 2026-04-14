"""Integration tests for admin services (servicios) API."""

import pytest
from app.models.models import ServicioBelleza


class TestListServices:
    """GET /api/admin/servicios"""

    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/servicios")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_data(self, admin_client, db_session):
        svc = ServicioBelleza(
            servicio="Corte", precio=150.0, duracion_minutos=30, activo=True, tenant_id=1,
        )
        db_session.add(svc)
        await db_session.commit()

        resp = await admin_client.get("/api/admin/servicios")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["servicio"] == "Corte"


class TestGetService:
    """GET /api/admin/servicios/{id}"""

    async def test_get_existing(self, admin_client, db_session):
        svc = ServicioBelleza(
            servicio="Tinte", precio=300.0, duracion_minutos=60, activo=True, tenant_id=1,
        )
        db_session.add(svc)
        await db_session.commit()
        await db_session.refresh(svc)

        resp = await admin_client.get(f"/api/admin/servicios/{svc.id}")
        assert resp.status_code == 200
        assert resp.json()["servicio"] == "Tinte"

    async def test_get_not_found(self, admin_client):
        resp = await admin_client.get("/api/admin/servicios/9999")
        assert resp.status_code == 404


class TestCreateService:
    """POST /api/admin/servicios"""

    async def test_create_success(self, admin_client):
        resp = await admin_client.post("/api/admin/servicios", json={
            "servicio": "Manicure",
            "precio": 200.0,
            "duracion_minutos": 45,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["servicio"] == "Manicure"
        assert data["id"] is not None

    async def test_create_duplicate_name(self, admin_client, db_session):
        svc = ServicioBelleza(
            servicio="Corte", precio=150.0, duracion_minutos=30, activo=True, tenant_id=1,
        )
        db_session.add(svc)
        await db_session.commit()

        resp = await admin_client.post("/api/admin/servicios", json={
            "servicio": "Corte",
            "precio": 200.0,
            "duracion_minutos": 30,
        })
        assert resp.status_code == 409

    async def test_create_viewer_forbidden(self, viewer_client):
        resp = await viewer_client.post("/api/admin/servicios", json={
            "servicio": "Test",
            "precio": 100.0,
            "duracion_minutos": 30,
        })
        assert resp.status_code == 403

    async def test_create_no_auth(self, app_client):
        resp = await app_client.post("/api/admin/servicios", json={
            "servicio": "Test",
            "precio": 100.0,
            "duracion_minutos": 30,
        })
        assert resp.status_code == 401


class TestUpdateService:
    """PUT /api/admin/servicios/{id}"""

    async def test_update_success(self, admin_client, db_session):
        svc = ServicioBelleza(
            servicio="Corte", precio=150.0, duracion_minutos=30, activo=True, tenant_id=1,
        )
        db_session.add(svc)
        await db_session.commit()
        await db_session.refresh(svc)

        resp = await admin_client.put(f"/api/admin/servicios/{svc.id}", json={
            "precio": 200.0,
        })
        assert resp.status_code == 200
        assert resp.json()["precio"] == 200.0
        assert resp.json()["servicio"] == "Corte"  # unchanged

    async def test_update_not_found(self, admin_client):
        resp = await admin_client.put("/api/admin/servicios/9999", json={
            "precio": 100.0,
        })
        assert resp.status_code == 404


class TestDeleteService:
    """DELETE /api/admin/servicios/{id}"""

    async def test_delete_success(self, admin_client, db_session):
        svc = ServicioBelleza(
            servicio="ToDelete", precio=100.0, duracion_minutos=15, activo=True, tenant_id=1,
        )
        db_session.add(svc)
        await db_session.commit()
        await db_session.refresh(svc)

        resp = await admin_client.delete(f"/api/admin/servicios/{svc.id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = await admin_client.get(f"/api/admin/servicios/{svc.id}")
        assert resp2.status_code == 404

    async def test_delete_not_found(self, admin_client):
        resp = await admin_client.delete("/api/admin/servicios/9999")
        assert resp.status_code == 404
