"""Integration tests for admin appointments (citas) API."""

import pytest
from datetime import datetime, timedelta, timezone
from app.models.models import Cita, EstadoCita


class TestListAppointments:
    """GET /api/admin/citas"""

    async def test_list_empty(self, admin_client):
        resp = await admin_client.get("/api/admin/citas")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_paginated(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        for i in range(3):
            cita = Cita(
                nombre_cliente=f"Cliente {i}",
                telefono_cliente="555000000" + str(i),
                inicio=now + timedelta(hours=i+1),
                fin=now + timedelta(hours=i+2),
                servicios=["Corte"],
                precio_total=150.0,
                estado=EstadoCita.PENDIENTE, tenant_id=1,
            )
            db_session.add(cita)
        await db_session.commit()

        resp = await admin_client.get("/api/admin/citas?page=1&page_size=2")
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1

    async def test_filter_by_estado(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita_pend = Cita(
            nombre_cliente="Pending",
            telefono_cliente="5550001",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=100.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        cita_comp = Cita(
            nombre_cliente="Completed",
            telefono_cliente="5550002",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=100.0,
            estado=EstadoCita.COMPLETADA, tenant_id=1,
        )
        db_session.add_all([cita_pend, cita_comp])
        await db_session.commit()

        resp = await admin_client.get("/api/admin/citas?estado=pendiente")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["nombre_cliente"] == "Pending"


class TestGetAppointment:
    """GET /api/admin/citas/{id}"""

    async def test_get_existing(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita = Cita(
            nombre_cliente="Juan",
            telefono_cliente="5551234567",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=150.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        db_session.add(cita)
        await db_session.commit()
        await db_session.refresh(cita)

        resp = await admin_client.get(f"/api/admin/citas/{cita.id}")
        assert resp.status_code == 200
        assert resp.json()["nombre_cliente"] == "Juan"

    async def test_get_not_found(self, admin_client):
        resp = await admin_client.get("/api/admin/citas/9999")
        assert resp.status_code == 404


class TestUpdateAppointment:
    """PUT /api/admin/citas/{id}"""

    async def test_update_success(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita = Cita(
            nombre_cliente="Original",
            telefono_cliente="5551234567",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=150.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        db_session.add(cita)
        await db_session.commit()
        await db_session.refresh(cita)

        resp = await admin_client.put(f"/api/admin/citas/{cita.id}", json={
            "notas": "Test note",
        })
        assert resp.status_code == 200
        assert resp.json()["notas"] == "Test note"

    async def test_update_not_found(self, admin_client):
        resp = await admin_client.put("/api/admin/citas/9999", json={
            "notas": "nope",
        })
        assert resp.status_code == 404


class TestChangeStatus:
    """PATCH /api/admin/citas/{id}/estado"""

    async def test_change_status(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita = Cita(
            nombre_cliente="Juan",
            telefono_cliente="555",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=100.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        db_session.add(cita)
        await db_session.commit()
        await db_session.refresh(cita)

        resp = await admin_client.patch(
            f"/api/admin/citas/{cita.id}/estado?estado=confirmada"
        )
        assert resp.status_code == 200
        assert resp.json()["estado"] == "confirmada"

    async def test_change_status_invalid(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita = Cita(
            nombre_cliente="Juan",
            telefono_cliente="555",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=100.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        db_session.add(cita)
        await db_session.commit()
        await db_session.refresh(cita)

        resp = await admin_client.patch(
            f"/api/admin/citas/{cita.id}/estado?estado=invalid_status"
        )
        assert resp.status_code == 400


class TestDeleteAppointment:
    """DELETE /api/admin/citas/{id}"""

    async def test_delete_success(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        cita = Cita(
            nombre_cliente="ToDelete",
            telefono_cliente="555",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=100.0,
            estado=EstadoCita.PENDIENTE,
            tenant_id=1,
        )
        db_session.add(cita)
        await db_session.commit()
        await db_session.refresh(cita)

        resp = await admin_client.delete(f"/api/admin/citas/{cita.id}")
        assert resp.status_code == 204

    async def test_delete_not_found(self, admin_client):
        resp = await admin_client.delete("/api/admin/citas/9999")
        assert resp.status_code == 404


class TestAppointmentsByStatus:
    """GET /api/admin/citas/stats/by-status"""

    async def test_by_status(self, admin_client, db_session):
        now = datetime.now(timezone.utc)
        for status in [EstadoCita.PENDIENTE, EstadoCita.PENDIENTE, EstadoCita.COMPLETADA]:
            cita = Cita(
                nombre_cliente="Test",
                telefono_cliente="555",
                inicio=now + timedelta(hours=1),
                fin=now + timedelta(hours=2),
                servicios=["Corte"],
                precio_total=100.0,
                estado=status, tenant_id=1,
            )
            db_session.add(cita)
        await db_session.commit()

        resp = await admin_client.get("/api/admin/citas/stats/by-status")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
