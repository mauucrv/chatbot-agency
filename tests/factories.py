"""Test data factories for creating model instances."""

from datetime import datetime, time, timezone, timedelta

from app.models.models import (
    AdminUser,
    Cita,
    ConversacionChatwoot,
    EstadisticasBot,
    EstadoCita,
    Estilista,
    HorarioEstilista,
    InformacionGeneral,
    KeywordHumano,
    RolAdmin,
    ServicioBelleza,
    DiaSemana,
)
from app.services.admin_auth_service import hash_password


def make_admin_user(**overrides) -> AdminUser:
    defaults = {
        "username": "testadmin",
        "password_hash": hash_password("testpass123"),
        "rol": RolAdmin.ADMIN,
        "activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return AdminUser(**defaults)


def make_viewer_user(**overrides) -> AdminUser:
    defaults = {
        "username": "testviewer",
        "password_hash": hash_password("viewerpass123"),
        "rol": RolAdmin.VIEWER,
        "activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return AdminUser(**defaults)


def make_servicio(**overrides) -> ServicioBelleza:
    defaults = {
        "servicio": "Corte de cabello",
        "descripcion": "Corte clásico",
        "precio": 150.0,
        "duracion_minutos": 30,
        "activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return ServicioBelleza(**defaults)


def make_estilista(**overrides) -> Estilista:
    defaults = {
        "nombre": "María López",
        "telefono": "5551234567",
        "email": "maria@test.com",
        "especialidades": ["Corte", "Color"],
        "activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return Estilista(**defaults)


def make_horario(estilista_id: int, **overrides) -> HorarioEstilista:
    defaults = {
        "estilista_id": estilista_id,
        "dia": DiaSemana.LUNES,
        "hora_inicio": time(9, 0),
        "hora_fin": time(18, 0),
        "activo": True,
    }
    defaults.update(overrides)
    return HorarioEstilista(**defaults)


def make_cita(**overrides) -> Cita:
    now = datetime.now(timezone.utc)
    defaults = {
        "nombre_cliente": "Juan Pérez",
        "telefono_cliente": "5551234567",
        "inicio": now + timedelta(hours=1),
        "fin": now + timedelta(hours=2),
        "servicios": ["Corte de cabello"],
        "precio_total": 150.0,
        "estado": EstadoCita.PENDIENTE,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return Cita(**defaults)


def make_info(**overrides) -> InformacionGeneral:
    defaults = {
        "nombre_salon": "Salón Test",
        "direccion": "Calle Test 123",
        "telefono": "5559876543",
        "horario": "Lunes a Sábado: 9:00 AM - 8:00 PM",
        "descripcion": "El mejor salón de pruebas",
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return InformacionGeneral(**defaults)


def make_keyword(**overrides) -> KeywordHumano:
    defaults = {
        "keyword": "operador",
        "activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return KeywordHumano(**defaults)


def make_estadistica(**overrides) -> EstadisticasBot:
    defaults = {
        "fecha": datetime.now(timezone.utc),
        "mensajes_recibidos": 50,
        "mensajes_respondidos": 45,
        "citas_creadas": 5,
        "citas_modificadas": 2,
        "citas_canceladas": 1,
        "transferencias_humano": 3,
        "errores": 0,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return EstadisticasBot(**defaults)


def make_conversacion(**overrides) -> ConversacionChatwoot:
    defaults = {
        "chatwoot_conversation_id": 1001,
        "telefono_cliente": "5551234567",
        "nombre_cliente": "Juan Pérez",
        "bot_activo": True,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return ConversacionChatwoot(**defaults)
