"""
Weekly statistics report job.
"""

import structlog
from datetime import datetime, timedelta

from sqlalchemy import select, func
import pytz

from app.config import settings
from app.database import get_session_context
from app.models import Cita, EstadisticasBot, Tenant
from app.services.chatwoot import get_chatwoot_service

logger = structlog.get_logger(__name__)


async def send_weekly_report() -> None:
    """
    Send weekly statistics report to each tenant's owner.

    Iterates all active tenants that have an owner_phone configured
    and sends a per-tenant summary of messages, appointments, and revenue.
    """
    logger.info("Starting weekly report job")

    try:
        # Get all active tenants with an owner phone
        async with get_session_context() as session:
            tenants_result = await session.execute(
                select(Tenant)
                .where(Tenant.activo == True)
                .where(Tenant.owner_phone.isnot(None))
            )
            tenants = tenants_result.scalars().all()

        if not tenants:
            logger.warning("No tenants with owner_phone configured, skipping reports")
            return

        for tenant in tenants:
            try:
                await _send_tenant_report(tenant)
            except Exception as e:
                logger.error(
                    "Error sending weekly report for tenant",
                    tenant_id=tenant.id, error=str(e),
                )

    except Exception as e:
        logger.error("Error in weekly report job", error=str(e))


async def _send_tenant_report(tenant: Tenant) -> None:
    """Send weekly report for a single tenant."""
    tz = pytz.timezone(tenant.timezone or settings.calendar_timezone)
    now = datetime.now(tz)
    week_start = (now - timedelta(days=7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    week_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    async with get_session_context() as session:
        # Get statistics for the week
        result = await session.execute(
            select(EstadisticasBot)
            .where(EstadisticasBot.tenant_id == tenant.id)
            .where(EstadisticasBot.fecha >= week_start)
            .where(EstadisticasBot.fecha <= week_end)
        )
        stats_records = result.scalars().all()

        # Aggregate statistics
        total_mensajes_recibidos = sum(s.mensajes_recibidos for s in stats_records)
        total_mensajes_respondidos = sum(s.mensajes_respondidos for s in stats_records)
        total_transferencias = sum(s.transferencias_humano for s in stats_records)
        total_errores = sum(s.errores for s in stats_records)

        # Calculate average response time
        response_times = [
            s.tiempo_respuesta_promedio_ms
            for s in stats_records
            if s.tiempo_respuesta_promedio_ms
        ]
        avg_response_time = (
            sum(response_times) / len(response_times)
            if response_times
            else 0
        )

        # Get appointment statistics from the appointments table
        result = await session.execute(
            select(Cita)
            .where(Cita.tenant_id == tenant.id)
            .where(Cita.inicio >= week_start)
            .where(Cita.inicio <= week_end)
        )
        appointments = result.scalars().all()

        completadas = [a for a in appointments if a.estado == "completada"]
        canceladas = [a for a in appointments if a.estado == "cancelada"]
        no_asistio = [a for a in appointments if a.estado == "no_asistio"]

        # Calculate revenue
        ingresos = sum(a.precio_total for a in completadas)

        # Get most popular services
        all_services = []
        for a in appointments:
            all_services.extend(a.servicios)

        service_counts = {}
        for service in all_services:
            service_counts[service] = service_counts.get(service, 0) + 1

        top_services = sorted(
            service_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

    # Format report message
    fecha_inicio = week_start.strftime("%d/%m/%Y")
    fecha_fin = week_end.strftime("%d/%m/%Y")

    message = (
        f"📊 *Reporte Semanal - {tenant.nombre}*\n"
        f"Período: {fecha_inicio} - {fecha_fin}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*💬 Mensajes*\n"
        f"• Recibidos: {total_mensajes_recibidos}\n"
        f"• Respondidos: {total_mensajes_respondidos}\n"
        f"• Transferencias a humano: {total_transferencias}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*📅 Citas*\n"
        f"• Agendadas: {len(appointments)}\n"
        f"• Completadas: {len(completadas)}\n"
        f"• Canceladas: {len(canceladas)}\n"
        f"• No asistieron: {len(no_asistio)}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*💰 Ingresos*\n"
        f"• Total estimado: {settings.currency_symbol}{ingresos:,.2f}\n\n"
    )

    if top_services:
        message += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*🌟 Servicios más solicitados*\n"
        )
        for service, count in top_services:
            message += f"• {service}: {count}\n"
        message += "\n"

    if avg_response_time > 0:
        message += (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"*⚡ Rendimiento del Bot*\n"
            f"• Tiempo de respuesta promedio: {avg_response_time:.0f}ms\n"
            f"• Errores: {total_errores}\n"
        )

    # Send report via tenant's Chatwoot
    try:
        chatwoot_svc = await get_chatwoot_service(tenant.id)
        result = await chatwoot_svc.send_message_to_phone(
            tenant.owner_phone,
            message,
        )

        if result:
            logger.info(
                "Weekly report sent",
                tenant_id=tenant.id,
                messages=total_mensajes_recibidos,
                appointments=len(appointments),
                revenue=ingresos,
            )
        else:
            logger.error("Failed to send weekly report", tenant_id=tenant.id)
    except Exception as e:
        logger.error(
            "Error sending weekly report via Chatwoot",
            tenant_id=tenant.id, error=str(e),
        )
