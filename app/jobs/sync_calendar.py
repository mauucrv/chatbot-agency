"""
Google Calendar synchronization job.
"""

import re
import structlog
from datetime import datetime, timedelta

from sqlalchemy import select, update
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita, Estilista, Tenant
from app.services.google_calendar import google_calendar_service

logger = structlog.get_logger(__name__)


async def sync_calendar_events() -> None:
    """
    Synchronize Google Calendar events with the database.

    Iterates all active tenants and for each:
    1. Fetches events from tenant's + per-stylist Google Calendars
    2. Checks for events that exist in Calendar but not in DB (external bookings)
    3. Checks for events deleted from Calendar but still in DB
    4. Updates appointment status based on event changes
    """
    logger.info("Starting calendar sync job")

    try:
        # Get all active tenants
        async with get_session_context() as session:
            tenants_result = await session.execute(
                select(Tenant).where(Tenant.activo == True)
            )
            tenants = tenants_result.scalars().all()

        for tenant in tenants:
            try:
                await _sync_tenant_calendar(tenant)
            except Exception as e:
                logger.error(
                    "Error syncing calendar for tenant",
                    tenant_id=tenant.id, error=str(e),
                )

    except Exception as e:
        logger.error("Error in calendar sync job", error=str(e))
        import traceback
        from app.services.telegram_notifier import notify_error
        await notify_error(
            "google_calendar",
            f"Calendar sync job failed: {str(e)}",
            traceback_str=traceback.format_exc(),
        )


async def _sync_tenant_calendar(tenant: Tenant) -> None:
    """Sync calendar events for a single tenant."""
    tz = pytz.timezone(tenant.timezone or settings.calendar_timezone)
    now = datetime.now(tz)
    start_time = now - timedelta(days=7)
    end_time = now + timedelta(days=30)

    # Collect all calendar IDs to sync (tenant's + per-stylist)
    calendar_ids_to_sync: set[str] = set()
    if tenant.google_calendar_id:
        calendar_ids_to_sync.add(tenant.google_calendar_id)
    elif settings.google_calendar_id:
        # Fallback to global calendar for default tenant
        calendar_ids_to_sync.add(settings.google_calendar_id)

    async with get_session_context() as session:
        result = await session.execute(
            select(Estilista.google_calendar_id)
            .where(Estilista.tenant_id == tenant.id)
            .where(Estilista.activo == True)
            .where(Estilista.google_calendar_id.isnot(None))
            .distinct()
        )
        for (cal_id,) in result.all():
            calendar_ids_to_sync.add(cal_id)

    if not calendar_ids_to_sync:
        return

    # Fetch events from all calendars
    calendar_events = []
    for cal_id in calendar_ids_to_sync:
        events = await google_calendar_service.list_events(
            start_time=start_time,
            end_time=end_time,
            max_results=500,
            calendar_id=cal_id,
        )
        if events is None:
            logger.error(
                "Failed to fetch calendar events",
                tenant_id=tenant.id, calendar_id=cal_id,
            )
            continue
        calendar_events.extend(events)

    logger.info(
        "Fetched calendar events for tenant",
        tenant_id=tenant.id,
        events=len(calendar_events),
        calendars=len(calendar_ids_to_sync),
    )

    async with get_session_context() as session:
        # Get existing appointments from database for this tenant
        result = await session.execute(
            select(Cita)
            .where(Cita.tenant_id == tenant.id)
            .where(Cita.inicio >= start_time)
            .where(Cita.inicio <= end_time)
        )
        db_appointments = {
            a.id_evento_google: a
            for a in result.scalars().all()
            if a.id_evento_google
        }

        processed_event_ids = set()
        new_events = 0
        updated_events = 0
        deleted_events = 0

        for event in calendar_events:
            event_id = event.get("id")
            if not event_id:
                continue

            processed_event_ids.add(event_id)

            if event_id in db_appointments:
                appointment = db_appointments[event_id]
                updated = await update_appointment_from_event(
                    session, appointment, event
                )
                if updated:
                    updated_events += 1
            else:
                created = await create_appointment_from_event(
                    session, event, tenant
                )
                if created:
                    new_events += 1

        # Check for deleted events (in DB but not in Calendar)
        for event_id, appointment in db_appointments.items():
            if event_id not in processed_event_ids:
                if appointment.estado not in ["cancelada", "completada"]:
                    appointment.estado = "cancelada"
                    appointment.notas = (
                        f"{appointment.notas or ''}\n"
                        "Cancelada automáticamente: evento eliminado del calendario"
                    ).strip()
                    deleted_events += 1
                    logger.info(
                        "Appointment marked as cancelled - event deleted",
                        tenant_id=tenant.id,
                        appointment_id=appointment.id,
                        event_id=event_id,
                    )

        await session.commit()

        logger.info(
            "Calendar sync completed for tenant",
            tenant_id=tenant.id,
            new=new_events,
            updated=updated_events,
            deleted=deleted_events,
        )


async def create_appointment_from_event(
    session, event: dict, tenant: Tenant
) -> bool:
    """
    Create a new appointment from a Google Calendar event.

    Args:
        session: Database session
        event: Google Calendar event
        tenant: The tenant this appointment belongs to

    Returns:
        True if appointment was created
    """
    try:
        tz = pytz.timezone(tenant.timezone or settings.calendar_timezone)
        event_id = event.get("id")
        summary = event.get("summary", "")
        description = event.get("description", "")

        # Parse start and end times
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        start_str = start_data.get("dateTime") or start_data.get("date")
        end_str = end_data.get("dateTime") or end_data.get("date")

        if not start_str or not end_str:
            return False

        # Parse datetimes
        if "T" in start_str:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        else:
            # All-day event - skip
            return False

        # Convert to local timezone
        start_dt = start_dt.astimezone(tz)
        end_dt = end_dt.astimezone(tz)

        # Parse summary: "Service1, Service2 - Client Name"
        servicios = []
        nombre_cliente = "Cliente externo"

        if " - " in summary:
            services_part, name_part = summary.rsplit(" - ", 1)
            servicios = [s.strip() for s in services_part.split(",")]
            nombre_cliente = name_part.strip()
        else:
            servicios = [summary]

        # Parse description for phone and price
        telefono_cliente = ""
        precio_total = 0.0
        estilista_nombre = None

        if description:
            phone_match = re.search(r"(?:Teléfono|Tel|Phone):\s*(\+?[\d\s-]+)", description, re.I)
            if phone_match:
                telefono_cliente = re.sub(r"\s|-", "", phone_match.group(1))

            price_match = re.search(r"(?:Precio|Price|Total):\s*\$?([\d,.]+)", description, re.I)
            if price_match:
                precio_total = float(price_match.group(1).replace(",", ""))

            stylist_match = re.search(r"Estilista:\s*(.+?)(?:\n|$)", description, re.I)
            if stylist_match:
                estilista_nombre = stylist_match.group(1).strip()

        # Find stylist if specified (scoped to tenant)
        estilista_id = None
        if estilista_nombre and estilista_nombre != "Por asignar":
            result = await session.execute(
                select(Estilista)
                .where(Estilista.tenant_id == tenant.id)
                .where(Estilista.nombre.ilike(f"%{estilista_nombre}%"))
                .where(Estilista.activo == True)
            )
            estilista = result.scalar_one_or_none()
            if estilista:
                estilista_id = estilista.id

        # Create appointment with tenant_id
        cita = Cita(
            nombre_cliente=nombre_cliente,
            telefono_cliente=telefono_cliente or "desconocido",
            inicio=start_dt,
            fin=end_dt,
            id_evento_google=event_id,
            servicios=servicios,
            precio_total=precio_total,
            estilista_id=estilista_id,
            notas="Sincronizado desde Google Calendar",
            tenant_id=tenant.id,
        )
        session.add(cita)

        logger.info(
            "Created appointment from calendar event",
            tenant_id=tenant.id,
            event_id=event_id,
            client=nombre_cliente,
        )

        return True

    except Exception as e:
        logger.error("Error creating appointment from event", error=str(e))
        return False


async def update_appointment_from_event(
    session, appointment: Cita, event: dict
) -> bool:
    """
    Update an existing appointment from a Google Calendar event.

    Args:
        session: Database session
        appointment: Existing appointment
        event: Google Calendar event

    Returns:
        True if appointment was updated
    """
    try:
        updated = False

        # Parse start and end times
        start_data = event.get("start", {})
        end_data = event.get("end", {})

        start_str = start_data.get("dateTime")
        end_str = end_data.get("dateTime")

        if start_str and end_str:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

            tz = pytz.timezone(settings.calendar_timezone)
            start_dt = start_dt.astimezone(tz)
            end_dt = end_dt.astimezone(tz)

            # Check if time changed
            if appointment.inicio != start_dt or appointment.fin != end_dt:
                appointment.inicio = start_dt
                appointment.fin = end_dt
                updated = True
                logger.info(
                    "Updated appointment time from calendar",
                    appointment_id=appointment.id,
                    new_start=start_dt.isoformat(),
                )

        # Check event status
        event_status = event.get("status")
        if event_status == "cancelled" and appointment.estado not in ["cancelada", "completada"]:
            appointment.estado = "cancelada"
            updated = True
            logger.info(
                "Appointment cancelled from calendar",
                appointment_id=appointment.id,
            )

        return updated

    except Exception as e:
        logger.error(
            "Error updating appointment from event",
            appointment_id=appointment.id,
            error=str(e),
        )
        return False
