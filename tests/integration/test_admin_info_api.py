"""Integration tests for admin salon info and keywords API."""

import pytest
from app.models.models import InformacionGeneral, KeywordHumano


class TestGetInfo:
    """GET /api/admin/info"""

    async def test_get_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/info")
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_get_with_data(self, admin_client, db_session):
        info = InformacionGeneral(
            nombre_salon="Test Salon",
            direccion="Calle 123",
            telefono="5551234567",
            tenant_id=1,
        )
        db_session.add(info)
        await db_session.commit()

        resp = await admin_client.get("/api/admin/info")
        assert resp.status_code == 200
        assert resp.json()["nombre_salon"] == "Test Salon"


class TestUpdateInfo:
    """PUT /api/admin/info"""

    async def test_create_when_none_exists(self, admin_client):
        resp = await admin_client.put("/api/admin/info", json={
            "nombre_salon": "New Salon",
            "direccion": "New Address",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["nombre_salon"] == "New Salon"
        assert data["id"] is not None

    async def test_update_existing(self, admin_client, db_session):
        info = InformacionGeneral(
            nombre_salon="Old Name",
            tenant_id=1,
        )
        db_session.add(info)
        await db_session.commit()

        resp = await admin_client.put("/api/admin/info", json={
            "nombre_salon": "Updated Name",
            "telefono": "5559999999",
        })
        assert resp.status_code == 200
        assert resp.json()["nombre_salon"] == "Updated Name"

    async def test_viewer_forbidden(self, viewer_client):
        resp = await viewer_client.put("/api/admin/info", json={
            "nombre_salon": "No Access",
        })
        assert resp.status_code == 403


class TestKeywords:
    """Keywords CRUD endpoints."""

    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/info/keywords")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_keyword(self, admin_client):
        resp = await admin_client.post("/api/admin/info/keywords", json={
            "keyword": "operador",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["keyword"] == "operador"
        assert data["activo"] is True

    async def test_create_duplicate(self, admin_client, db_session):
        kw = KeywordHumano(keyword="operador", activo=True, tenant_id=1)
        db_session.add(kw)
        await db_session.commit()

        resp = await admin_client.post("/api/admin/info/keywords", json={
            "keyword": "operador",
        })
        assert resp.status_code == 409

    async def test_toggle_keyword(self, admin_client, db_session):
        kw = KeywordHumano(keyword="test", activo=True, tenant_id=1)
        db_session.add(kw)
        await db_session.commit()
        await db_session.refresh(kw)

        resp = await admin_client.put(
            f"/api/admin/info/keywords/{kw.id}?activo=false"
        )
        assert resp.status_code == 200
        assert resp.json()["activo"] is False

    async def test_toggle_not_found(self, admin_client):
        resp = await admin_client.put(
            "/api/admin/info/keywords/9999?activo=false"
        )
        assert resp.status_code == 404

    async def test_delete_keyword(self, admin_client, db_session):
        kw = KeywordHumano(keyword="delete-me", activo=True, tenant_id=1)
        db_session.add(kw)
        await db_session.commit()
        await db_session.refresh(kw)

        resp = await admin_client.delete(f"/api/admin/info/keywords/{kw.id}")
        assert resp.status_code == 204

    async def test_delete_not_found(self, admin_client):
        resp = await admin_client.delete("/api/admin/info/keywords/9999")
        assert resp.status_code == 404
