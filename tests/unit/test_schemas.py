"""Tests for Pydantic schema validation."""

import pytest
from datetime import datetime, timezone, timedelta, time
from pydantic import ValidationError

from app.schemas.schemas import (
    AppointmentCreate,
    AppointmentUpdate,
    AvailabilityCheck,
    ChatwootWebhookPayload,
    SalonInfoBase,
    ServiceCreate,
    ServiceUpdate,
    StylistCreate,
    StylistScheduleBase,
)


class TestChatwootWebhookPayload:
    """Webhook payload schema."""

    def test_minimal_payload(self):
        p = ChatwootWebhookPayload(event="message_created")
        assert p.event == "message_created"
        assert p.conversation is None

    def test_full_payload(self):
        p = ChatwootWebhookPayload(
            event="message_created",
            id=1,
            content="Hola",
            message_type="incoming",
            conversation={"id": 123, "status": "open"},
        )
        assert p.conversation.id == 123

    def test_empty_payload_is_valid(self):
        p = ChatwootWebhookPayload()
        assert p.event is None


class TestServiceSchemas:
    """Service create/update validation."""

    def test_service_create_valid(self):
        s = ServiceCreate(
            servicio="Corte",
            precio=100.0,
            duracion_minutos=30,
        )
        assert s.servicio == "Corte"

    def test_service_create_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            ServiceCreate(servicio="", precio=100.0, duracion_minutos=30)

    def test_service_create_rejects_negative_price(self):
        with pytest.raises(ValidationError):
            ServiceCreate(servicio="Corte", precio=-10.0, duracion_minutos=30)

    def test_service_create_allows_zero_price(self):
        """Free services (e.g. 'Consulta gratuita') are valid."""
        s = ServiceCreate(servicio="Consulta gratuita", precio=0, duracion_minutos=30)
        assert s.precio == 0

    def test_service_create_rejects_zero_duration(self):
        with pytest.raises(ValidationError):
            ServiceCreate(servicio="Corte", precio=100, duracion_minutos=0)

    def test_service_update_partial(self):
        s = ServiceUpdate(precio=200.0)
        assert s.precio == 200.0
        assert s.servicio is None


class TestAppointmentSchemas:
    """Appointment create/update validation."""

    def test_create_valid(self):
        now = datetime.now(timezone.utc)
        a = AppointmentCreate(
            nombre_cliente="Juan",
            telefono_cliente="5551234567",
            inicio=now + timedelta(hours=1),
            fin=now + timedelta(hours=2),
            servicios=["Corte"],
            precio_total=150.0,
        )
        assert a.nombre_cliente == "Juan"

    def test_create_rejects_naive_datetime(self):
        now = datetime.now()  # naive
        with pytest.raises(ValidationError, match="timezone-aware"):
            AppointmentCreate(
                nombre_cliente="Juan",
                telefono_cliente="555",
                inicio=now,
                fin=now + timedelta(hours=1),
                servicios=["Corte"],
                precio_total=100.0,
            )

    def test_create_rejects_end_before_start(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="after start"):
            AppointmentCreate(
                nombre_cliente="Juan",
                telefono_cliente="555",
                inicio=now + timedelta(hours=2),
                fin=now + timedelta(hours=1),
                servicios=["Corte"],
                precio_total=100.0,
            )

    def test_update_partial(self):
        u = AppointmentUpdate(notas="Updated note")
        assert u.notas == "Updated note"
        assert u.nombre_cliente is None


class TestStylistSchemas:
    """Stylist schema validation."""

    def test_create_valid(self):
        s = StylistCreate(nombre="Maria")
        assert s.nombre == "Maria"

    def test_create_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            StylistCreate(nombre="")


class TestAvailabilitySchema:
    """Availability check validation."""

    def test_rejects_zero_duration(self):
        with pytest.raises(ValidationError):
            AvailabilityCheck(
                fecha=datetime.now(timezone.utc),
                duracion_minutos=0,
            )

    def test_valid(self):
        a = AvailabilityCheck(
            fecha=datetime.now(timezone.utc),
            duracion_minutos=30,
        )
        assert a.duracion_minutos == 30


class TestSalonInfoSchema:
    """Salon info validation."""

    def test_valid(self):
        info = SalonInfoBase(nombre_salon="Mi Salon")
        assert info.nombre_salon == "Mi Salon"

    def test_rejects_missing_name(self):
        with pytest.raises(ValidationError):
            SalonInfoBase()
