"""
Appointment reminder job.
"""

import structlog
from datetime import datetime, timedelta

from sqlalchemy import select, update
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita, Tenant
from app.services.chatwoot import get_chatwoot_service

logger = structlog.get_logger(__name__)


async def send_appointment_reminders() -> None:
    """
    Send reminders for appointments scheduled for tomorrow.

    Iterates all active tenants and sends WhatsApp messages to clients
    with appointments scheduled for the next day.
    """
    logger.info("Starting appointment reminders job")

    try:
        # Get all active tenants
        async with get_session_context() as session:
            tenants_result = await session.execute(
                select(Tenant).where(Tenant.activo == True)
            )
            tenants = tenants_result.scalars().all()

        total_sent = 0
        total_failed = 0

        for tenant in tenants:
            tz = pytz.timezone(tenant.timezone or settings.calendar_timezone)
            now = datetime.now(tz)
            tomorrow_start = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            tomorrow_end = tomorrow_start + timedelta(days=1)

            try:
                chatwoot_svc = await get_chatwoot_service(tenant.id)
            except Exception as e:
                logger.warning(
                    "Could not get Chatwoot service for tenant, skipping reminders",
                    tenant_id=tenant.id, error=str(e),
                )
                continue

            # Load tenant's salon name for the reminder message
            from app.models import InformacionGeneral
            async with get_session_context() as session:
                info_result = await session.execute(
                    select(InformacionGeneral.nombre_salon)
                    .where(InformacionGeneral.tenant_id == tenant.id)
                    .limit(1)
                )
                salon_name = info_result.scalar_one_or_none() or tenant.nombre

                # Get tomorrow's appointments for this tenant
                result = await session.execute(
                    select(Cita)
                    .where(Cita.tenant_id == tenant.id)
                    .where(Cita.inicio >= tomorrow_start)
                    .where(Cita.inicio < tomorrow_end)
                    .where(Cita.estado.in_(["pendiente", "confirmada"]))
                    .where(Cita.recordatorio_enviado == False)
                )
                appointments = result.scalars().all()

                if not appointments:
                    continue

                for appointment in appointments:
                    try:
                        hora = appointment.inicio.strftime("%H:%M")
                        servicios = ", ".join(appointment.servicios)

                        message = (
                            f"📅 *Recordatorio de cita*\n\n"
                            f"Hola {appointment.nombre_cliente}!\n\n"
                            f"Te recordamos que tienes una cita mañana:\n\n"
                            f"🕐 Hora: {hora}\n"
                            f"💇 Servicios: {servicios}\n"
                            f"💰 Total: {settings.currency_symbol}{appointment.precio_total:.2f}\n\n"
                            f"¡Te esperamos en {salon_name}!\n\n"
                            f"Si necesitas cancelar o modificar tu cita, "
                            f"responde a este mensaje."
                        )

                        send_result = await chatwoot_svc.send_message_to_phone(
                            appointment.telefono_cliente,
                            message,
                        )

                        if send_result:
                            appointment.recordatorio_enviado = True
                            total_sent += 1
                            logger.info(
                                "Reminder sent",
                                tenant_id=tenant.id,
                                appointment_id=appointment.id,
                                phone=appointment.telefono_cliente[-4:],
                            )
                        else:
                            total_failed += 1
                            logger.warning(
                                "Failed to send reminder",
                                tenant_id=tenant.id,
                                appointment_id=appointment.id,
                            )

                    except Exception as e:
                        total_failed += 1
                        logger.error(
                            "Error sending reminder",
                            tenant_id=tenant.id,
                            appointment_id=appointment.id,
                            error=str(e),
                        )

                await session.commit()

        logger.info(
            "Appointment reminders job completed",
            sent=total_sent,
            failed=total_failed,
        )

    except Exception as e:
        logger.error("Error in appointment reminders job", error=str(e))
        import traceback
        from app.services.telegram_notifier import notify_error
        await notify_error(
            "database",
            f"Appointment reminders job failed: {str(e)}",
            traceback_str=traceback.format_exc(),
        )
