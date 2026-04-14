"""Integration tests for admin stylists (estilistas) API."""

import pytest
from app.models.models import Estilista, HorarioEstilista, DiaSemana
from datetime import time


class TestListStylists:
    """GET /api/admin/estilistas"""

    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/estilistas")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_data(self, admin_client, db_session):
        stylist = Estilista(nombre="Ana", activo=True, tenant_id=1)
        db_session.add(stylist)
        await db_session.commit()

        resp = await admin_client.get("/api/admin/estilistas")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["nombre"] == "Ana"


class TestGetStylist:
    """GET /api/admin/estilistas/{id}"""

    async def test_get_existing(self, admin_client, db_session):
        stylist = Estilista(nombre="Pedro", activo=True, tenant_id=1)
        db_session.add(stylist)
        await db_session.commit()
        await db_session.refresh(stylist)

        resp = await admin_client.get(f"/api/admin/estilistas/{stylist.id}")
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Pedro"

    async def test_get_not_found(self, admin_client):
        resp = await admin_client.get("/api/admin/estilistas/9999")
        assert resp.status_code == 404


class TestCreateStylist:
    """POST /api/admin/estilistas"""

    async def test_create_success(self, admin_client):
        resp = await admin_client.post("/api/admin/estilistas", json={
            "nombre": "Carlos",
            "telefono": "5551234567",
            "especialidades": ["Corte", "Barba"],
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["nombre"] == "Carlos"
        assert data["id"] is not None

    async def test_create_viewer_forbidden(self, viewer_client):
        resp = await viewer_client.post("/api/admin/estilistas", json={
            "nombre": "Test",
        })
        assert resp.status_code == 403


class TestUpdateStylist:
    """PUT /api/admin/estilistas/{id}"""

    async def test_update_success(self, admin_client, db_session):
        stylist = Estilista(nombre="Ana", activo=True, tenant_id=1)
        db_session.add(stylist)
        await db_session.commit()
        await db_session.refresh(stylist)

        resp = await admin_client.put(f"/api/admin/estilistas/{stylist.id}", json={
            "nombre": "Ana García",
        })
        assert resp.status_code == 200
        assert resp.json()["nombre"] == "Ana García"

    async def test_update_not_found(self, admin_client):
        resp = await admin_client.put("/api/admin/estilistas/9999", json={
            "nombre": "Nobody",
        })
        assert resp.status_code == 404


class TestDeleteStylist:
    """DELETE /api/admin/estilistas/{id}"""

    async def test_delete_success(self, admin_client, db_session):
        stylist = Estilista(nombre="ToDelete", activo=True, tenant_id=1)
        db_session.add(stylist)
        await db_session.commit()
        await db_session.refresh(stylist)

        resp = await admin_client.delete(f"/api/admin/estilistas/{stylist.id}")
        assert resp.status_code == 204

    async def test_delete_not_found(self, admin_client):
        resp = await admin_client.delete("/api/admin/estilistas/9999")
        assert resp.status_code == 404


class TestReplaceSchedules:
    """PUT /api/admin/estilistas/{id}/horarios"""

    async def test_replace_schedules(self, admin_client, db_session):
        stylist = Estilista(nombre="Ana", activo=True, tenant_id=1)
        db_session.add(stylist)
        await db_session.commit()
        await db_session.refresh(stylist)

        resp = await admin_client.put(
            f"/api/admin/estilistas/{stylist.id}/horarios",
            json=[
                {"dia": "lunes", "hora_inicio": "09:00:00", "hora_fin": "18:00:00"},
                {"dia": "martes", "hora_inicio": "10:00:00", "hora_fin": "17:00:00"},
            ],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["dia"] == "lunes"

    async def test_replace_schedules_not_found(self, admin_client):
        resp = await admin_client.put(
            "/api/admin/estilistas/9999/horarios",
            json=[{"dia": "lunes", "hora_inicio": "09:00:00", "hora_fin": "18:00:00"}],
        )
        assert resp.status_code == 404
