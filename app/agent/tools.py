"""
LangChain tools for the AgencyBot agent.
"""

import contextvars
import re
import structlog
from datetime import datetime, time, timedelta
from typing import List, Optional

from langchain.tools import tool
from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload
import pytz

from app.config import settings
from app.context import get_current_tenant_id
from app.database import get_session_context
from app.models import (
    Cita, DetalleVenta, Estilista, HorarioEstilista, InformacionGeneral,
    Producto, ServicioBelleza, Venta,
)
from app.services.google_calendar import google_calendar_service
from app.services.redis_cache import redis_cache

logger = structlog.get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.calendar_timezone)

# Server-side authenticated phone — set by the agent before tool execution.
# Tools use this instead of trusting the LLM-provided phone number.
_authenticated_phone: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_authenticated_phone", default=None
)

# Chatwoot conversation and contact IDs — set by the agent before tool execution.
# Used for updating labels and custom attributes in Chatwoot.
_conversation_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "_conversation_id", default=None
)
_contact_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "_contact_id", default=None
)


def set_authenticated_phone(phone: Optional[str]) -> None:
    """Set the authenticated phone for the current async context."""
    _authenticated_phone.set(phone)


def get_authenticated_phone() -> Optional[str]:
    """Get the authenticated phone for the current async context."""
    return _authenticated_phone.get()


def set_conversation_context(conversation_id: Optional[int], contact_id: Optional[int]) -> None:
    """Set the Chatwoot conversation and contact IDs for the current async context."""
    _conversation_id.set(conversation_id)
    _contact_id.set(contact_id)


def get_conversation_id() -> Optional[int]:
    """Get the Chatwoot conversation ID for the current async context."""
    return _conversation_id.get()


def get_contact_id() -> Optional[int]:
    """Get the Chatwoot contact ID for the current async context."""
    return _contact_id.get()


def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only for consistent matching."""
    return re.sub(r"[^\d]", "", phone)


def escape_ilike(value: str) -> str:
    """Escape ILIKE special characters (%, _) in user input."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _get_tenant_id() -> int:
    """Get current tenant ID from async context. Raises ValueError if not set."""
    tid = get_current_tenant_id()
    if not tid:
        raise ValueError("Tenant context not set — cannot process tool call outside of a tenant scope")
    return tid


# Days of week in Spanish (Monday=0 ... Sunday=6), matching Python's weekday()
DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _parse_fecha_hora(fecha: str, hora: str) -> datetime:
    """Parse 'YYYY-MM-DD' + 'HH:MM' into a TZ-aware datetime. Raises ValueError."""
    dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
    return TZ.localize(dt)


def _parse_fecha(fecha: str) -> datetime:
    """Parse 'YYYY-MM-DD' into a TZ-aware datetime (midnight). Raises ValueError."""
    dt = datetime.strptime(fecha, "%Y-%m-%d")
    return TZ.localize(dt)


def _validate_booking_window(dt: datetime, *, action: str = "verificar disponibilidad") -> Optional[str]:
    """Check date is not past and within max booking window. Returns error string or None."""
    now = datetime.now(TZ)
    if dt < now:
        return f"No puedo {action} para fechas pasadas."
    max_date = now + timedelta(days=settings.max_booking_days_ahead)
    if dt > max_date:
        return f"Solo puedo {action} hasta {settings.max_booking_days_ahead} dias en el futuro."
    return None


def _get_dia_semana(dt: datetime) -> str:
    """Return Spanish day name for a datetime."""
    return DIAS_SEMANA[dt.weekday()]


async def _find_estilista(session, tenant_id: int, nombre: str):
    """Find active stylist by ILIKE name match with horarios pre-loaded."""
    result = await session.execute(
        select(Estilista)
        .where(Estilista.tenant_id == tenant_id)
        .where(Estilista.nombre.ilike(f"%{escape_ilike(nombre)}%"))
        .where(Estilista.activo == True)
        .options(selectinload(Estilista.horarios))
    )
    return result.scalar_one_or_none()


def _get_horario_dia(estilista, dia: str):
    """Get the active schedule entry for a stylist on a given day. Returns HorarioEstilista or None."""
    if not estilista or not hasattr(estilista, "horarios"):
        return None
    for h in estilista.horarios:
        if h.activo and h.dia.value == dia:
            return h
    return None


def _validate_horario(estilista, dt: datetime, end_dt: datetime) -> Optional[str]:
    """Validate appointment against stylist schedule or default business hours. Returns error or None."""
    dia = _get_dia_semana(dt)

    if estilista and hasattr(estilista, "horarios") and estilista.horarios:
        horario_dia = _get_horario_dia(estilista, dia)
        if not horario_dia:
            return f"{estilista.nombre} no trabaja los {dia}s. Por favor elige otro dia."
        if dt.time() < horario_dia.hora_inicio or end_dt.time() > horario_dia.hora_fin:
            return (
                f"El horario solicitado esta fuera del horario de {estilista.nombre} "
                f"({horario_dia.hora_inicio.strftime('%H:%M')} - {horario_dia.hora_fin.strftime('%H:%M')}). "
                f"Por favor elige un horario dentro de ese rango."
            )
    else:
        start_limit = time(settings.default_business_start_hour, 0)
        end_limit = time(settings.default_business_end_hour, 0)
        if dt.time() < start_limit or end_dt.time() > end_limit:
            return (
                f"El horario solicitado esta fuera del horario de atencion "
                f"({settings.default_business_start_hour:02d}:00 - {settings.default_business_end_hour:02d}:00). "
                f"Por favor elige un horario dentro de ese rango."
            )
    return None


async def _resolve_servicios(session, tenant_id: int, servicios_str: str):
    """Resolve comma-separated service names. Returns (names, duration_min, price) or error string."""
    servicios_lista = [s.strip() for s in servicios_str.split(",")]
    total_duracion = 0
    total_precio = 0.0
    encontrados = []

    for nombre in servicios_lista:
        result = await session.execute(
            select(ServicioBelleza)
            .where(ServicioBelleza.tenant_id == tenant_id)
            .where(ServicioBelleza.servicio.ilike(f"%{escape_ilike(nombre)}%"))
            .where(ServicioBelleza.activo == True)
        )
        servicio = result.scalar_one_or_none()
        if servicio:
            total_duracion += servicio.duracion_minutos
            total_precio += servicio.precio
            encontrados.append(servicio.servicio)
        else:
            all_svc = await session.execute(
                select(ServicioBelleza.servicio)
                .where(ServicioBelleza.tenant_id == tenant_id)
                .where(ServicioBelleza.activo == True)
            )
            available = [s[0] for s in all_svc.all()]
            return (
                f"No encontre el servicio '{nombre}'. "
                f"Servicios disponibles: {', '.join(available)}. "
                f"Usa el nombre exacto del servicio."
            )

    if not encontrados:
        return "No se encontraron servicios validos."
    return (encontrados, total_duracion, total_precio)


async def _get_tenant_calendar_id() -> Optional[str]:
    """Load the tenant's google_calendar_id from DB. Returns None if not set."""
    try:
        tenant_id = _get_tenant_id()
        from app.models import Tenant
        async with get_session_context() as session:
            result = await session.execute(
                select(Tenant.google_calendar_id).where(Tenant.id == tenant_id)
            )
            return result.scalar_one_or_none()
    except Exception:
        return None


# ============================================================
# Tool 1: List Services
# ============================================================


@tool
async def list_services() -> str:
    """
    Lista todos los servicios disponibles.
    Incluye nombre del servicio, precio, duracion en minutos y consultores que lo ofrecen.
    Usa esta herramienta cuando el prospecto pregunte por servicios, precios o que ofrecemos.
    """
    try:
        tenant_id = _get_tenant_id()
        # Try cache first
        cached = await redis_cache.get_services(tenant_id)
        if cached:
            services = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(
                    select(ServicioBelleza).where(
                        ServicioBelleza.activo == True,
                        ServicioBelleza.tenant_id == tenant_id,
                    )
                )
                services_db = result.scalars().all()
                services = [
                    {
                        "servicio": s.servicio,
                        "descripcion": s.descripcion,
                        "precio": s.precio,
                        "duracion_minutos": s.duracion_minutos,
                        "estilistas_disponibles": s.estilistas_disponibles or [],
                    }
                    for s in services_db
                ]
                # Cache the result
                await redis_cache.set_services(tenant_id, services)

        if not services:
            return "No hay servicios disponibles en este momento."

        # Format response
        lines = ["Servicios disponibles:\n"]
        for s in services:
            line = f"- {s['servicio']}: {settings.currency_symbol}{s['precio']:.2f} ({s['duracion_minutos']} min)"
            if s.get("descripcion"):
                line += f"\n  {s['descripcion']}"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error listing services", error=str(e))
        return "Error al obtener la lista de servicios. Por favor intenta mas tarde."


# ============================================================
# Tool 2: List Stylists
# ============================================================


@tool
async def list_stylists() -> str:
    """
    Lista todos los estilistas activos del salon.
    Incluye nombre, especialidades y horario de trabajo.
    Usa esta herramienta cuando el cliente pregunte por estilistas disponibles.
    """
    try:
        tenant_id = _get_tenant_id()
        # Try cache first
        cached = await redis_cache.get_stylists(tenant_id)
        if cached:
            stylists = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(
                    select(Estilista)
                    .where(Estilista.activo == True, Estilista.tenant_id == tenant_id)
                    .options(selectinload(Estilista.horarios))
                )
                stylists_db = result.scalars().all()
                stylists = []
                for st in stylists_db:
                    horarios = []
                    for h in st.horarios:
                        if h.activo:
                            horarios.append({
                                "dia": h.dia.value,
                                "hora_inicio": h.hora_inicio.strftime("%H:%M"),
                                "hora_fin": h.hora_fin.strftime("%H:%M"),
                            })
                    stylists.append({
                        "id": st.id,
                        "nombre": st.nombre,
                        "especialidades": st.especialidades or [],
                        "horarios": horarios,
                    })
                # Cache the result
                await redis_cache.set_stylists(tenant_id, stylists)

        if not stylists:
            return "No hay estilistas disponibles en este momento."

        # Format response
        lines = ["Nuestros estilistas:\n"]
        for st in stylists:
            line = f"- {st['nombre']}"
            if st.get("especialidades"):
                line += f"\n  Especialidades: {', '.join(st['especialidades'])}"
            if st.get("horarios"):
                dias = [h["dia"].capitalize() for h in st["horarios"]]
                line += f"\n  Dias: {', '.join(dias)}"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error listing stylists", error=str(e))
        return "Error al obtener la lista de estilistas. Por favor intenta mas tarde."


# ============================================================
# Tool 3: List Salon Info
# ============================================================


@tool
async def list_info() -> str:
    """
    Obtiene la informacion general del salon.
    Incluye nombre, direccion, telefono, horario de atencion y politicas.
    Usa esta herramienta cuando el cliente pregunte donde estamos, horarios, o informacion del salon.
    """
    try:
        tenant_id = _get_tenant_id()
        # Try cache first
        cached = await redis_cache.get_info(tenant_id)
        if cached:
            info = cached
        else:
            # Fetch from database
            async with get_session_context() as session:
                result = await session.execute(
                    select(InformacionGeneral)
                    .where(InformacionGeneral.tenant_id == tenant_id)
                    .limit(1)
                )
                info_db = result.scalar_one_or_none()

                if info_db:
                    info = {
                        "nombre_salon": info_db.nombre_salon,
                        "direccion": info_db.direccion,
                        "telefono": info_db.telefono,
                        "horario": info_db.horario,
                        "descripcion": info_db.descripcion,
                        "politicas": info_db.politicas,
                    }
                    await redis_cache.set_info(tenant_id, info)
                else:
                    # Use defaults from settings
                    info = {
                        "nombre_salon": settings.salon_name,
                        "direccion": settings.salon_address,
                        "telefono": settings.salon_phone,
                        "horario": settings.salon_hours,
                    }

        # Format response
        lines = [f"{info.get('nombre_salon', 'Nuestro Salon')}\n"]
        if info.get("descripcion"):
            lines.append(f"{info['descripcion']}\n")
        if info.get("direccion"):
            lines.append(f"Direccion: {info['direccion']}")
        if info.get("telefono"):
            lines.append(f"Telefono: {info['telefono']}")
        if info.get("horario"):
            lines.append(f"Horario: {info['horario']}")
        if info.get("politicas"):
            lines.append(f"\nPoliticas: {info['politicas']}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting salon info", error=str(e))
        return "Error al obtener la informacion del salon. Por favor intenta mas tarde."


# ============================================================
# Tool 4: Check Availability (FreeBusy API)
# ============================================================


@tool
async def check_availability(
    fecha: str,
    hora: str,
    duracion_minutos: int = 60,
) -> str:
    """
    Verifica si hay disponibilidad en una fecha y hora especifica usando Google Calendar FreeBusy API.
    Si la hora exacta no esta disponible, sugiere horarios alternativos.

    Args:
        fecha: Fecha en formato YYYY-MM-DD (ej: 2024-03-15)
        hora: Hora en formato HH:MM (ej: 14:30)
        duracion_minutos: Duracion del servicio en minutos (default: 60)
    """
    try:
        # Parse date and time
        try:
            dt = _parse_fecha_hora(fecha, hora)
        except ValueError:
            return "Formato de fecha/hora invalido. Usa fecha: YYYY-MM-DD y hora: HH:MM"

        window_err = _validate_booking_window(dt, action="verificar disponibilidad")
        if window_err:
            return window_err

        # Calculate end time
        end_dt = dt + timedelta(minutes=duracion_minutos)
        dia = _get_dia_semana(dt)
        schedule_start_hour = settings.default_business_start_hour
        schedule_end_hour = settings.default_business_end_hour

        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            db_result = await session.execute(
                select(Estilista)
                .where(Estilista.tenant_id == tenant_id)
                .where(Estilista.activo == True)
                .options(selectinload(Estilista.horarios))
            )
            estilistas = db_result.scalars().all()

            if estilistas:
                available_consultant = False
                horarios_del_dia = []
                for est in estilistas:
                    h = _get_horario_dia(est, dia)
                    if h:
                        horarios_del_dia.append(h)
                        if dt.time() >= h.hora_inicio and end_dt.time() <= h.hora_fin:
                            available_consultant = True

                if not horarios_del_dia:
                    return f"No hay atencion los {dia}s."

                if not available_consultant:
                    ranges = [f"{h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}" for h in horarios_del_dia]
                    return (
                        f"El horario {hora} esta fuera del horario de atencion los {dia}s. "
                        f"Horario disponible: {', '.join(ranges)}. "
                        f"Por favor elige un horario dentro de ese rango."
                    )

                schedule_start_hour = min(h.hora_inicio.hour for h in horarios_del_dia)
                schedule_end_hour = max(h.hora_fin.hour for h in horarios_del_dia)
            else:
                err = _validate_horario(None, dt, end_dt)
                if err:
                    return err

        # Check Google Calendar availability (use tenant's calendar)
        tenant_calendar_id = await _get_tenant_calendar_id()
        result = await google_calendar_service.check_availability(dt, end_dt, calendar_id=tenant_calendar_id)

        if result.get("error"):
            return f"Error al verificar disponibilidad: {result['error']}"

        if result["available"]:
            return f"Hay disponibilidad! El horario {fecha} a las {hora} esta libre para un servicio de {duracion_minutos} minutos."
        else:
            # Get alternative slots within actual business hours
            day_start = dt.replace(hour=schedule_start_hour, minute=0)
            slots = await google_calendar_service.get_available_slots(
                day_start, duracion_minutos,
                start_hour=schedule_start_hour,
                end_hour=schedule_end_hour,
                calendar_id=tenant_calendar_id,
            )

            if slots:
                alternatives = []
                for slot in slots[:5]:  # Show max 5 alternatives
                    slot_time = slot["start"].strftime("%H:%M")
                    alternatives.append(slot_time)

                return (
                    f"El horario {fecha} a las {hora} no esta disponible.\n\n"
                    f"Horarios disponibles para ese dia:\n- " + "\n- ".join(alternatives)
                )
            else:
                return (
                    f"El horario {fecha} a las {hora} no esta disponible "
                    "y no encontre otros horarios libres para ese dia."
                )

    except Exception as e:
        logger.error("Error checking availability", error=str(e))
        return "Error al verificar disponibilidad. Por favor intenta mas tarde."


# ============================================================
# Tool 5: Check Stylist Availability
# ============================================================


@tool
async def check_stylist_availability(
    estilista_nombre: str,
    fecha: str,
    duracion_minutos: int = 60,
) -> str:
    """
    Verifica la disponibilidad de un estilista especifico para una fecha.
    Muestra los horarios libres del estilista ese dia.

    Args:
        estilista_nombre: Nombre del estilista
        fecha: Fecha en formato YYYY-MM-DD
        duracion_minutos: Duracion del servicio en minutos
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            estilista = await _find_estilista(session, tenant_id, estilista_nombre)
            if not estilista:
                return f"No encontre un estilista con el nombre '{estilista_nombre}'."

            try:
                dt = _parse_fecha(fecha)
            except ValueError:
                return "Formato de fecha invalido. Usa: YYYY-MM-DD"

            window_err = _validate_booking_window(dt, action="verificar disponibilidad")
            if window_err:
                return window_err

            dia = _get_dia_semana(dt)
            horario_dia = _get_horario_dia(estilista, dia)
            if not horario_dia:
                return f"{estilista.nombre} no trabaja los {dia}s."

            # Get available slots using calendar (per-stylist if configured, else tenant's)
            cal_id = estilista.google_calendar_id or await _get_tenant_calendar_id()
            result = await google_calendar_service.get_available_slots(
                dt, duracion_minutos,
                start_hour=horario_dia.hora_inicio.hour,
                end_hour=horario_dia.hora_fin.hour,
                calendar_id=cal_id,
            )

            if result:
                slots = [s["start"].strftime("%H:%M") for s in result[:8]]
                return (
                    f"Disponibilidad de {estilista.nombre} el {fecha}:\n\n"
                    f"Horario de trabajo: {horario_dia.hora_inicio.strftime('%H:%M')} - {horario_dia.hora_fin.strftime('%H:%M')}\n\n"
                    f"Horarios disponibles:\n- " + "\n- ".join(slots)
                )
            else:
                return f"{estilista.nombre} no tiene horarios disponibles el {fecha}."

    except Exception as e:
        logger.error("Error checking stylist availability", error=str(e))
        return "Error al verificar disponibilidad del estilista."


# ============================================================
# Tool 6: Check Stylist Schedule
# ============================================================


@tool
async def check_stylist_schedule(estilista_nombre: str) -> str:
    """
    Obtiene el horario de trabajo semanal de un estilista.

    Args:
        estilista_nombre: Nombre del estilista
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            estilista = await _find_estilista(session, tenant_id, estilista_nombre)
            if not estilista:
                return f"No encontre un estilista con el nombre '{estilista_nombre}'."

            if not estilista.horarios:
                return f"{estilista.nombre} no tiene horario registrado."

            # Format schedule
            lines = [f"Horario de {estilista.nombre}:\n"]
            horarios_por_dia = {h.dia.value: h for h in estilista.horarios if h.activo}

            for dia in DIAS_SEMANA:
                if dia in horarios_por_dia:
                    h = horarios_por_dia[dia]
                    lines.append(
                        f"- {dia.capitalize()}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}"
                    )

            if len(lines) == 1:
                return f"{estilista.nombre} no tiene dias de trabajo activos."

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting stylist schedule", error=str(e))
        return "Error al obtener el horario del estilista."


# ============================================================
# Tool 7: Check Stylist for Service
# ============================================================


@tool
async def check_stylist_for_service(servicio_nombre: str) -> str:
    """
    Encuentra que estilistas pueden realizar un servicio especifico.

    Args:
        servicio_nombre: Nombre del servicio
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            result = await session.execute(
                select(ServicioBelleza)
                .where(ServicioBelleza.tenant_id == tenant_id)
                .where(ServicioBelleza.servicio.ilike(f"%{escape_ilike(servicio_nombre)}%"))
                .where(ServicioBelleza.activo == True)
            )
            servicio = result.scalar_one_or_none()

            if not servicio:
                return f"No encontre un servicio llamado '{servicio_nombre}'."

            estilistas_disponibles = servicio.estilistas_disponibles or []

            if not estilistas_disponibles:
                # If no specific stylists, all active stylists can do it
                result = await session.execute(
                    select(Estilista)
                    .where(Estilista.tenant_id == tenant_id)
                    .where(Estilista.activo == True)
                )
                estilistas = result.scalars().all()
                nombres = [e.nombre for e in estilistas]
            else:
                nombres = estilistas_disponibles

            if not nombres:
                return f"No hay estilistas disponibles para {servicio.servicio}."

            return (
                f"Estilistas que realizan {servicio.servicio}:\n\n"
                f"- " + "\n- ".join(nombres) + "\n\n"
                f"Precio: {settings.currency_symbol}{servicio.precio:.2f}\n"
                f"Duracion: {servicio.duracion_minutos} minutos"
            )

    except Exception as e:
        logger.error("Error checking stylist for service", error=str(e))
        return "Error al buscar estilistas para el servicio."


# ============================================================
# Tool 8: Get Stylist Info
# ============================================================


@tool
async def get_stylist_info(estilista_nombre: str) -> str:
    """
    Obtiene informacion detallada de un estilista.

    Args:
        estilista_nombre: Nombre del estilista
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            estilista = await _find_estilista(session, tenant_id, estilista_nombre)
            if not estilista:
                return f"No encontre un estilista con el nombre '{estilista_nombre}'."

            lines = [f"{estilista.nombre}\n"]

            if estilista.especialidades:
                lines.append(f"Especialidades: {', '.join(estilista.especialidades)}")

            if estilista.horarios:
                lines.append("\nHorario de trabajo:")
                for h in estilista.horarios:
                    if h.activo:
                        lines.append(
                            f"- {h.dia.value.capitalize()}: "
                            f"{h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}"
                        )

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting stylist info", error=str(e))
        return "Error al obtener informacion del estilista."


# ============================================================
# Tool 9: Create Booking
# ============================================================


@tool
async def create_booking(
    nombre_cliente: str,
    telefono_cliente: str,
    servicios: str,
    fecha: str,
    hora: str,
    estilista_nombre: Optional[str] = None,
    notas: Optional[str] = None,
) -> str:
    """
    Crea una nueva cita en el calendario y la base de datos.
    IMPORTANTE: Confirma todos los detalles con el cliente antes de crear la cita.

    Args:
        nombre_cliente: Nombre completo del cliente
        telefono_cliente: Telefono del cliente
        servicios: Lista de servicios separados por coma (ej: "Corte, Tinte")
        fecha: Fecha en formato YYYY-MM-DD
        hora: Hora en formato HH:MM
        estilista_nombre: Nombre del estilista preferido (opcional)
        notas: Notas adicionales (opcional)
    """
    slot_key = None
    try:
        # Use authenticated phone — reject if unavailable to prevent prompt injection
        auth_phone = get_authenticated_phone()
        if not auth_phone:
            return "Error: no se pudo verificar el número de teléfono del cliente. Por favor intenta de nuevo."
        telefono_cliente = auth_phone

        # Validate client name — reject generic placeholders
        nombre_lower = nombre_cliente.strip().lower()
        if nombre_lower in ("cliente", "client", "usuario", "user", "desconocido", "unknown", ""):
            return "Necesito el nombre del cliente para crear la cita. Por favor pregunta su nombre."

        # Normalize phone once for all DB operations
        telefono_normalizado = normalize_phone(telefono_cliente)
        tenant_id = _get_tenant_id()

        # Resolve services from DB
        async with get_session_context() as session:
            svc_result = await _resolve_servicios(session, tenant_id, servicios)
            if isinstance(svc_result, str):
                return svc_result
            servicios_encontrados, total_duracion, total_precio = svc_result

            # Check active appointments limit
            max_appointments = settings.max_active_appointments_per_user
            if max_appointments > 0:
                now = datetime.now(TZ)
                count_result = await session.execute(
                    select(func.count())
                    .select_from(Cita)
                    .where(Cita.tenant_id == tenant_id)
                    .where(Cita.telefono_cliente == telefono_normalizado)
                    .where(Cita.inicio > now)
                    .where(Cita.estado.in_(["pendiente", "confirmada"]))
                )
                active_count = count_result.scalar()
                if active_count >= max_appointments:
                    return (
                        f"Ya tienes {active_count} cita(s) activa(s). "
                        f"El maximo permitido es {max_appointments}. "
                        f"Por favor cancela o espera a que se complete una cita antes de agendar otra."
                    )

            # Find stylist if specified
            tenant_calendar_id = await _get_tenant_calendar_id()
            estilista_id = None
            estilista_nombre_real = None
            estilista_calendar_id = None
            estilista_obj = None
            if estilista_nombre:
                estilista_obj = await _find_estilista(session, tenant_id, estilista_nombre)
                if estilista_obj:
                    estilista_id = estilista_obj.id
                    estilista_nombre_real = estilista_obj.nombre
                    estilista_calendar_id = estilista_obj.google_calendar_id

            # Parse date and time
            try:
                dt = _parse_fecha_hora(fecha, hora)
            except ValueError:
                return "Formato de fecha/hora invalido. Usa fecha: YYYY-MM-DD y hora: HH:MM"

            window_err = _validate_booking_window(dt, action="crear citas")
            if window_err:
                return window_err

            end_dt = dt + timedelta(minutes=total_duracion)

            # Validate against consultant's work schedule
            horario_err = _validate_horario(estilista_obj, dt, end_dt)
            if horario_err:
                return horario_err

            # Acquire distributed lock to prevent double-booking (TOCTOU fix)
            slot_key = f"{fecha}T{hora}:{estilista_id or 'any'}"
            if not await redis_cache.acquire_booking_lock(tenant_id, slot_key, ttl=30):
                return (
                    "Alguien mas esta reservando este horario en este momento. "
                    "Por favor intenta de nuevo en unos segundos o elige otro horario."
                )

            # Check availability (inside lock, on stylist's or tenant's calendar)
            effective_calendar_id = estilista_calendar_id or tenant_calendar_id
            availability = await google_calendar_service.check_availability(
                dt, end_dt, calendar_id=effective_calendar_id
            )
            if not availability["available"]:
                await redis_cache.release_booking_lock(tenant_id, slot_key)
                return (
                    f"El horario {fecha} a las {hora} no esta disponible. "
                    "Por favor elige otro horario."
                )

            # Create Google Calendar event
            summary = f"{', '.join(servicios_encontrados)} - {nombre_cliente}"
            description = (
                f"Telefono: {telefono_cliente}\n"
                f"Servicios: {', '.join(servicios_encontrados)}\n"
                f"Precio Total: {settings.currency_symbol}{total_precio:.2f}\n"
                f"Estilista: {estilista_nombre_real or 'Por asignar'}"
            )
            if notas:
                description += f"\nNotas: {notas}"

            event = await google_calendar_service.create_event(
                summary=summary,
                description=description,
                start_time=dt,
                end_time=end_dt,
                calendar_id=effective_calendar_id,
            )

            if not event:
                await redis_cache.release_booking_lock(tenant_id, slot_key)
                return "Error al crear la cita en el calendario. Por favor intenta mas tarde."

            # Save to database
            cita = Cita(
                nombre_cliente=nombre_cliente,
                telefono_cliente=telefono_normalizado,
                inicio=dt,
                fin=end_dt,
                id_evento_google=event.get("id"),
                servicios=servicios_encontrados,
                precio_total=total_precio,
                estilista_id=estilista_id,
                notas=notas,
                tenant_id=tenant_id,
            )
            session.add(cita)

            # Auto-advance lead stage and update servicio_interes
            if telefono_normalizado:
                from app.models.models import Lead, EtapaLead
                await session.execute(
                    update(Lead)
                    .where(
                        Lead.telefono == telefono_normalizado,
                        Lead.tenant_id == tenant_id,
                        Lead.etapa.in_([EtapaLead.NUEVO, EtapaLead.CONTACTADO]),
                    )
                    .values(
                        etapa=EtapaLead.CITA_AGENDADA,
                        servicio_interes=", ".join(servicios_encontrados),
                    )
                )

            await session.commit()

            # Release lock after successful commit
            await redis_cache.release_booking_lock(tenant_id, slot_key)
            slot_key = None  # Prevent double release in finally

            # Fire-and-forget: update Chatwoot labels and contact attributes
            try:
                conv_id = get_conversation_id()
                cw_contact_id = get_contact_id()
                from app.services.chatwoot import get_chatwoot_service
                _cw = await get_chatwoot_service(tenant_id)
                if conv_id:
                    await _cw.add_labels(conv_id, ["cita-agendada"])
                if cw_contact_id:
                    await _cw.update_contact_custom_attributes(
                        cw_contact_id,
                        {"servicio_interes": ", ".join(servicios_encontrados)},
                    )
            except Exception as e:
                logger.warning("Failed to update Chatwoot metadata after booking", error=str(e))

            # Format confirmation
            return (
                f"Cita agendada exitosamente!\n\n"
                f"Fecha: {fecha}\n"
                f"Hora: {hora}\n"
                f"Duracion: {total_duracion} minutos\n"
                f"Servicios: {', '.join(servicios_encontrados)}\n"
                f"Precio total: {settings.currency_symbol}{total_precio:.2f}\n"
                + (f"Estilista: {estilista_nombre_real}\n" if estilista_nombre_real else "")
                + f"\nTe esperamos!"
            )

    except Exception as e:
        logger.error("Error creating booking", error=str(e))
        return "Error al crear la cita. Por favor intenta mas tarde."
    finally:
        if slot_key:
            await redis_cache.release_booking_lock(tenant_id, slot_key)


# ============================================================
# Tool 10: Update Booking
# ============================================================


@tool
async def update_booking(
    nueva_fecha: Optional[str] = None,
    nueva_hora: Optional[str] = None,
    nuevos_servicios: Optional[str] = None,
    nuevo_estilista: Optional[str] = None,
) -> str:
    """
    Modifica la proxima cita existente del cliente actual.
    Solo modifica los campos proporcionados.
    No necesitas pedir el telefono, se obtiene automaticamente.

    Args:
        nueva_fecha: Nueva fecha en formato YYYY-MM-DD (opcional)
        nueva_hora: Nueva hora en formato HH:MM (opcional)
        nuevos_servicios: Nuevos servicios separados por coma (opcional)
        nuevo_estilista: Nuevo estilista (opcional)
    """
    try:
        auth_phone = get_authenticated_phone()
        if not auth_phone:
            return "No pude identificar tu numero de telefono. Por favor contacta al salon directamente."

        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            # Find the next appointment for this phone (exact match on normalized number)
            now = datetime.now(TZ)
            telefono_normalizado = normalize_phone(auth_phone)
            result = await session.execute(
                select(Cita)
                .where(Cita.tenant_id == tenant_id)
                .where(Cita.telefono_cliente == telefono_normalizado)
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
                .options(selectinload(Cita.estilista).selectinload(Estilista.horarios))
            )
            cita = result.scalar_one_or_none()

            if not cita:
                return "No encontre citas pendientes para tu numero."

            # Current stylist's calendar (for per-stylist calendar support), fall back to tenant's
            tenant_calendar_id = await _get_tenant_calendar_id()
            current_calendar_id = (
                (cita.estilista.google_calendar_id if cita.estilista else None)
                or tenant_calendar_id
            )

            # Track changes
            cambios = []

            # Update date/time if provided
            if nueva_fecha or nueva_hora:
                fecha = nueva_fecha or cita.inicio.strftime("%Y-%m-%d")
                hora = nueva_hora or cita.inicio.strftime("%H:%M")

                try:
                    nuevo_inicio = _parse_fecha_hora(fecha, hora)
                except ValueError:
                    return "Formato de fecha/hora invalido."

                window_err = _validate_booking_window(nuevo_inicio, action="reagendar citas")
                if window_err:
                    return window_err

                # Calculate duration from current appointment
                duracion = (cita.fin - cita.inicio).total_seconds() / 60
                nuevo_fin = nuevo_inicio + timedelta(minutes=duracion)

                # Validate against consultant's work schedule
                horario_err = _validate_horario(cita.estilista, nuevo_inicio, nuevo_fin)
                if horario_err:
                    return horario_err

                # Check availability excluding current event (on stylist's calendar)
                availability = await google_calendar_service.check_availability(
                    nuevo_inicio, nuevo_fin, calendar_id=current_calendar_id
                )

                # If not available, check if the conflict is only with our own event
                if not availability["available"] and cita.id_evento_google:
                    # Re-check: the busy period might be our own event
                    busy_periods = availability.get("busy_periods", [])
                    only_self_conflict = True
                    for busy in busy_periods:
                        # If the busy period exactly matches our current event time, it's us
                        busy_start = busy["start"].astimezone(TZ)
                        busy_end = busy["end"].astimezone(TZ)
                        if not (busy_start == cita.inicio and busy_end == cita.fin):
                            only_self_conflict = False
                            break

                    if not only_self_conflict:
                        return (
                            f"El nuevo horario {fecha} a las {hora} no esta disponible. "
                            "Por favor elige otro horario."
                        )
                elif not availability["available"]:
                    return (
                        f"El nuevo horario {fecha} a las {hora} no esta disponible. "
                        "Por favor elige otro horario."
                    )

                cita.inicio = nuevo_inicio
                cita.fin = nuevo_fin
                cambios.append(f"Fecha/hora: {fecha} a las {hora}")

            # Update services if provided
            if nuevos_servicios:
                svc_result = await _resolve_servicios(session, tenant_id, nuevos_servicios)
                if isinstance(svc_result, str):
                    return svc_result
                servicios_encontrados, total_duracion, total_precio = svc_result
                cita.servicios = servicios_encontrados
                cita.precio_total = total_precio
                cita.fin = cita.inicio + timedelta(minutes=total_duracion)
                cambios.append(f"Servicios: {', '.join(servicios_encontrados)}")

            # Update stylist if provided
            new_calendar_id = current_calendar_id
            if nuevo_estilista:
                estilista = await _find_estilista(session, tenant_id, nuevo_estilista)
                if estilista:
                    horario_err = _validate_horario(estilista, cita.inicio, cita.fin)
                    if horario_err:
                        return horario_err

                    cita.estilista_id = estilista.id
                    new_calendar_id = estilista.google_calendar_id or tenant_calendar_id
                    cambios.append(f"Estilista: {estilista.nombre}")

            if not cambios:
                return "No se especificaron cambios para realizar."

            # Update Google Calendar event
            if cita.id_evento_google:
                summary = f"{', '.join(cita.servicios)} - {cita.nombre_cliente}"
                description = (
                    f"Telefono: {cita.telefono_cliente}\n"
                    f"Servicios: {', '.join(cita.servicios)}\n"
                    f"Precio Total: {settings.currency_symbol}{cita.precio_total:.2f}"
                )

                # If calendar changed (stylist with different calendar), migrate event
                resolved_old = google_calendar_service._resolve_calendar_id(current_calendar_id)
                resolved_new = google_calendar_service._resolve_calendar_id(new_calendar_id)
                if resolved_old != resolved_new:
                    # Delete from old calendar
                    await google_calendar_service.delete_event(
                        cita.id_evento_google, calendar_id=current_calendar_id
                    )
                    # Create in new calendar
                    new_event = await google_calendar_service.create_event(
                        summary=summary,
                        description=description,
                        start_time=cita.inicio,
                        end_time=cita.fin,
                        calendar_id=new_calendar_id,
                    )
                    if new_event:
                        cita.id_evento_google = new_event.get("id")
                else:
                    await google_calendar_service.update_event(
                        event_id=cita.id_evento_google,
                        summary=summary,
                        description=description,
                        start_time=cita.inicio,
                        end_time=cita.fin,
                        calendar_id=current_calendar_id,
                    )

            await session.commit()

            return (
                f"Cita modificada exitosamente\n\n"
                f"Cambios realizados:\n- " + "\n- ".join(cambios) + "\n\n"
                f"Nueva fecha: {cita.inicio.strftime('%Y-%m-%d')}\n"
                f"Nueva hora: {cita.inicio.strftime('%H:%M')}\n"
                f"Precio total: {settings.currency_symbol}{cita.precio_total:.2f}"
            )

    except Exception as e:
        logger.error("Error updating booking", error=str(e))
        return "Error al modificar la cita. Por favor intenta mas tarde."


# ============================================================
# Tool 11: Cancel Booking
# ============================================================


@tool
async def cancel_booking(
    motivo: Optional[str] = None,
) -> str:
    """
    Cancela la proxima cita del cliente actual.
    IMPORTANTE: Confirma con el cliente antes de cancelar.
    No necesitas pedir el telefono, se obtiene automaticamente.

    Args:
        motivo: Motivo de la cancelacion (opcional)
    """
    try:
        auth_phone = get_authenticated_phone()
        if not auth_phone:
            return "No pude identificar tu numero de telefono. Por favor contacta al salon directamente."

        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            # Find the next appointment for this phone (exact match)
            now = datetime.now(TZ)
            telefono_normalizado = normalize_phone(auth_phone)
            result = await session.execute(
                select(Cita)
                .where(Cita.tenant_id == tenant_id)
                .where(Cita.telefono_cliente == telefono_normalizado)
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
                .options(selectinload(Cita.estilista))
            )
            cita = result.scalar_one_or_none()

            if not cita:
                return "No encontre citas pendientes para tu numero."

            # Store appointment details for confirmation message
            fecha = cita.inicio.strftime("%Y-%m-%d")
            hora = cita.inicio.strftime("%H:%M")
            servicios = ", ".join(cita.servicios)

            # Delete from Google Calendar (use stylist's calendar, fall back to tenant's)
            if cita.id_evento_google:
                cal_id = (
                    (cita.estilista.google_calendar_id if cita.estilista else None)
                    or await _get_tenant_calendar_id()
                )
                await google_calendar_service.delete_event(
                    cita.id_evento_google, calendar_id=cal_id
                )

            # Update status in database
            cita.estado = "cancelada"
            if motivo:
                cita.notas = f"{cita.notas or ''}\nMotivo cancelacion: {motivo}".strip()

            await session.commit()

            # Fire-and-forget: remove cita-agendada label
            try:
                conv_id = get_conversation_id()
                if conv_id:
                    from app.services.chatwoot import get_chatwoot_service
                    _cw = await get_chatwoot_service(tenant_id)
                    await _cw.remove_labels(conv_id, ["cita-agendada"])
            except Exception as e:
                logger.warning("Failed to remove cita-agendada label after cancellation", error=str(e))

            return (
                f"Cita cancelada\n\n"
                f"Fecha: {fecha}\n"
                f"Hora: {hora}\n"
                f"Servicios: {servicios}\n"
                + (f"Motivo: {motivo}\n" if motivo else "")
                + "\nEsperamos verte pronto."
            )

    except Exception as e:
        logger.error("Error canceling booking", error=str(e))
        return "Error al cancelar la cita. Por favor intenta mas tarde."


# ============================================================
# Tool 12: Get Appointments
# ============================================================


@tool
async def get_appointments() -> str:
    """
    Consulta las citas del cliente actual.
    Muestra citas pendientes y las ultimas citas completadas.
    No necesitas pedir el telefono, se obtiene automaticamente.
    """
    try:
        auth_phone = get_authenticated_phone()
        if not auth_phone:
            return "No pude identificar tu numero de telefono. Por favor contacta al salon directamente."

        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            now = datetime.now(TZ)
            telefono_normalizado = normalize_phone(auth_phone)

            # Get upcoming appointments (exact match on normalized phone)
            result = await session.execute(
                select(Cita)
                .where(Cita.tenant_id == tenant_id)
                .where(Cita.telefono_cliente == telefono_normalizado)
                .where(Cita.inicio > now)
                .where(Cita.estado.in_(["pendiente", "confirmada"]))
                .order_by(Cita.inicio)
            )
            proximas = result.scalars().all()

            # Get past appointments (last 3)
            result = await session.execute(
                select(Cita)
                .where(Cita.tenant_id == tenant_id)
                .where(Cita.telefono_cliente == telefono_normalizado)
                .where(Cita.inicio <= now)
                .order_by(Cita.inicio.desc())
                .limit(3)
            )
            pasadas = result.scalars().all()

            if not proximas and not pasadas:
                return "No encontre citas registradas para tu numero."

            lines = ["Tus citas:\n"]

            if proximas:
                lines.append("Proximas citas:")
                for cita in proximas:
                    status_icon = "[Confirmada]" if cita.estado == "confirmada" else "[Pendiente]"
                    lines.append(
                        f"{status_icon} {cita.inicio.strftime('%Y-%m-%d %H:%M')} - "
                        f"{', '.join(cita.servicios)} ({settings.currency_symbol}{cita.precio_total:.2f})"
                    )
                lines.append("")

            if pasadas:
                lines.append("Ultimas citas:")
                for cita in pasadas:
                    status = "[OK]" if cita.estado == "completada" else "[X]"
                    lines.append(
                        f"{status} {cita.inicio.strftime('%Y-%m-%d')} - "
                        f"{', '.join(cita.servicios)}"
                    )

            return "\n".join(lines)

    except Exception as e:
        logger.error("Error getting appointments", error=str(e))
        return "Error al consultar las citas. Por favor intenta mas tarde."


# ============================================================
# Tool 13: Update Prospect Info
# ============================================================


@tool
async def update_prospect_info(tipo_negocio: str) -> str:
    """
    Actualiza la informacion del prospecto cuando menciona su tipo de negocio.
    Usa esta herramienta cuando el prospecto te diga que tipo de negocio tiene
    (ej: "tengo un restaurante", "soy dentista", "tengo una estetica").

    Args:
        tipo_negocio: El tipo de negocio del prospecto (ej: "Restaurante", "Clinica dental", "Estetica")
    """
    try:
        # Update internal CRM lead
        tenant_id = _get_tenant_id()
        auth_phone = get_authenticated_phone()
        if auth_phone:
            try:
                from app.models.models import Lead
                async with get_session_context() as session:
                    telefono = normalize_phone(auth_phone)
                    await session.execute(
                        update(Lead)
                        .where(Lead.tenant_id == tenant_id)
                        .where(Lead.telefono == telefono)
                        .values(empresa=tipo_negocio)
                    )
                    await session.commit()
            except Exception as e:
                logger.warning("Failed to update Lead.empresa", error=str(e))

        # Update Chatwoot contact custom attributes
        contact_id = get_contact_id()
        if contact_id:
            try:
                from app.services.chatwoot import get_chatwoot_service
                _cw = await get_chatwoot_service(tenant_id)
                await _cw.update_contact_custom_attributes(
                    contact_id, {"tipo_negocio": tipo_negocio}
                )
            except Exception as e:
                logger.warning("Failed to update Chatwoot custom attributes", error=str(e))

        return f"Informacion del prospecto actualizada: tipo de negocio = {tipo_negocio}."
    except Exception as e:
        logger.warning("Error updating prospect info", error=str(e))
        return f"Informacion registrada: tipo de negocio = {tipo_negocio}."


# ============================================================
# Tool 14: List Products
# ============================================================


@tool
async def list_products(categoria: str = "") -> str:
    """
    Lista los productos disponibles para venta.
    Muestra nombre, marca, precio y disponibilidad.
    Usa esta herramienta cuando el cliente pregunte por productos, precios de productos,
    o qué productos venden/manejan.

    Args:
        categoria: Filtrar por categoria (opcional). Valores: "reventa" para productos de venta al cliente,
                   "uso_salon" para productos de uso interno. Dejar vacio para mostrar todos los de venta.
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            query = (
                select(Producto)
                .where(Producto.tenant_id == tenant_id)
                .where(Producto.activo == True)
            )
            # By default show only retail products (reventa), unless specifically asked
            if categoria:
                query = query.where(Producto.categoria == categoria)
            else:
                query = query.where(Producto.categoria == "reventa")

            query = query.order_by(Producto.nombre)
            result = await session.execute(query)
            productos = result.scalars().all()

        if not productos:
            return "No hay productos disponibles en este momento."

        lines = ["Productos disponibles:\n"]
        for p in productos:
            stock_label = "Disponible" if p.cantidad > 0 else "Agotado"
            line = f"- {p.nombre}"
            if p.marca:
                line += f" ({p.marca})"
            if p.precio_venta:
                line += f": {settings.currency_symbol}{p.precio_venta:.2f}"
            line += f" — {stock_label}"
            if p.subcategoria:
                line += f" [{p.subcategoria}]"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error listing products", error=str(e))
        return "Error al obtener la lista de productos. Por favor intenta mas tarde."


# ============================================================
# Tool 15: Search Product
# ============================================================


@tool
async def search_product(nombre: str) -> str:
    """
    Busca un producto especifico por nombre y devuelve informacion detallada.
    Usa esta herramienta cuando el cliente pregunte por un producto en particular,
    su precio, o si esta disponible.

    Args:
        nombre: Nombre o parte del nombre del producto a buscar (ej: "shampoo", "cera", "tratamiento")
    """
    try:
        tenant_id = _get_tenant_id()
        async with get_session_context() as session:
            result = await session.execute(
                select(Producto)
                .where(Producto.tenant_id == tenant_id)
                .where(Producto.activo == True)
                .where(Producto.nombre.ilike(f"%{escape_ilike(nombre)}%"))
                .order_by(Producto.nombre)
            )
            productos = result.scalars().all()

        if not productos:
            return f"No encontre productos con el nombre '{nombre}'. Usa la herramienta list_products para ver todos los productos disponibles."

        lines = []
        for p in productos:
            stock_label = f"{p.cantidad} en stock" if p.cantidad > 0 else "Agotado"
            line = f"- {p.nombre}"
            if p.marca:
                line += f" | Marca: {p.marca}"
            if p.subcategoria:
                line += f" | Categoria: {p.subcategoria}"
            if p.precio_venta:
                line += f" | Precio: {settings.currency_symbol}{p.precio_venta:.2f}"
            line += f" | {stock_label}"
            lines.append(line)

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error searching product", error=str(e))
        return "Error al buscar el producto. Por favor intenta mas tarde."


# ============================================================
# Tool 16: Create Product Order
# ============================================================


@tool
async def create_product_order(productos_pedido: str, nombre_cliente: str, notas: str = "") -> str:
    """
    Registra un pedido de productos para un cliente.
    IMPORTANTE: Confirma los productos, cantidades y el total con el cliente antes de registrar.

    Args:
        productos_pedido: Productos y cantidades separados por coma.
                         Formato: "nombre_producto:cantidad" (ej: "Shampoo Kerastase:2, Cera para cabello:1")
        nombre_cliente: Nombre del cliente que hace el pedido
        notas: Notas adicionales del pedido (ej: "Recoger en sucursal", "Entregar en proxima cita")
    """
    try:
        auth_phone = get_authenticated_phone()
        if not auth_phone:
            return "Error: no se pudo verificar el número de teléfono del cliente. Por favor intenta de nuevo."

        tenant_id = _get_tenant_id()

        # Parse products from input
        items = []
        for item_str in productos_pedido.split(","):
            item_str = item_str.strip()
            if ":" in item_str:
                nombre, cant_str = item_str.rsplit(":", 1)
                try:
                    cantidad = int(cant_str.strip())
                except ValueError:
                    return f"Cantidad invalida para '{nombre.strip()}'. Usa formato: nombre:cantidad"
                if cantidad < 1:
                    return f"La cantidad debe ser al menos 1 para '{nombre.strip()}'."
                items.append((nombre.strip(), cantidad))
            else:
                items.append((item_str.strip(), 1))

        if not items:
            return "No se especificaron productos. Usa formato: 'Producto:cantidad, Producto2:cantidad'"

        async with get_session_context() as session:
            detalles = []
            total = 0.0

            for nombre, cantidad in items:
                result = await session.execute(
                    select(Producto)
                    .where(Producto.tenant_id == tenant_id)
                    .where(Producto.activo == True)
                    .where(Producto.nombre.ilike(f"%{escape_ilike(nombre)}%"))
                )
                producto = result.scalar_one_or_none()

                if not producto:
                    return (
                        f"No encontre el producto '{nombre}'. "
                        f"Usa la herramienta list_products para ver los productos disponibles."
                    )

                if not producto.precio_venta:
                    return f"El producto '{producto.nombre}' no tiene precio de venta configurado."

                if producto.cantidad < cantidad:
                    if producto.cantidad == 0:
                        return f"'{producto.nombre}' esta agotado."
                    return (
                        f"Solo hay {producto.cantidad} unidades de '{producto.nombre}' disponibles, "
                        f"pero se solicitaron {cantidad}."
                    )

                subtotal = producto.precio_venta * cantidad
                total += subtotal
                detalles.append({
                    "producto": producto,
                    "cantidad": cantidad,
                    "subtotal": subtotal,
                })

            # Create the sale record
            venta = Venta(
                tipo="producto",
                subtotal=total,
                descuento=0.0,
                total=total,
                metodo_pago="efectivo",
                notas=f"Pedido por WhatsApp — Cliente: {nombre_cliente}. {notas}".strip(),
                vendedor="Bot WhatsApp",
                tenant_id=tenant_id,
            )
            session.add(venta)
            await session.flush()

            # Create line items and update stock
            for det in detalles:
                detalle_venta = DetalleVenta(
                    venta_id=venta.id,
                    producto_id=det["producto"].id,
                    descripcion=det["producto"].nombre,
                    cantidad=det["cantidad"],
                    precio_unitario=det["producto"].precio_venta,
                    subtotal=det["subtotal"],
                )
                session.add(detalle_venta)

                # Decrease stock
                det["producto"].cantidad -= det["cantidad"]

            await session.commit()

        # Format confirmation
        lines = [f"Pedido #{venta.id} registrado:\n"]
        for det in detalles:
            lines.append(
                f"- {det['producto'].nombre} x{det['cantidad']}: "
                f"{settings.currency_symbol}{det['subtotal']:.2f}"
            )
        lines.append(f"\nTotal: {settings.currency_symbol}{total:.2f}")
        if notas:
            lines.append(f"Notas: {notas}")

        return "\n".join(lines)

    except Exception as e:
        logger.error("Error creating product order", error=str(e))
        return "Error al registrar el pedido. Por favor intenta mas tarde."


# ============================================================
# Export all tools
# ============================================================


def get_tools() -> List:
    """Get all tools for the agent."""
    return [
        list_services,
        list_stylists,
        list_info,
        check_availability,
        check_stylist_availability,
        check_stylist_schedule,
        check_stylist_for_service,
        get_stylist_info,
        create_booking,
        update_booking,
        cancel_booking,
        get_appointments,
        update_prospect_info,
        list_products,
        search_product,
        create_product_order,
    ]
