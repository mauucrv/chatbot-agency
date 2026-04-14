"""
Admin dashboard endpoint — aggregated metrics for today, cached in Redis (60s TTL).
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.config import settings
from app.database import get_session_context
from app.models.models import (
    AdminUser,
    Cita,
    EstadoCita,
    EstadisticasBot,
    Estilista,
    Lead,
    ServicioBelleza,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import get_current_admin

import pytz

router = APIRouter(prefix="/dashboard", tags=["Admin Dashboard"])

DASHBOARD_CACHE_TTL = 60  # seconds


class UsageResumen(BaseModel):
    mensajes_mes: int = 0
    mensajes_audio_mes: int = 0
    mensajes_imagen_mes: int = 0
    tokens_openai_mes: int = 0
    usuarios_unicos_hoy: int = 0


class DashboardMetrics(BaseModel):
    citas_hoy: int
    citas_pendientes: int
    citas_completadas_hoy: int
    ingresos_hoy: float
    total_servicios: int
    total_estilistas: int
    mensajes_hoy: int
    errores_hoy: int
    total_leads: int
    leads_nuevos_hoy: int
    leads_en_pipeline: int
    seguimientos_pendientes: int
    uso: UsageResumen
    citas_semana: list[dict]
    citas_recientes: list[dict]


@router.get("", response_model=DashboardMetrics)
async def get_dashboard(admin: AdminUser = Depends(get_current_admin)):
    # Try cache first
    cached = await redis_cache.get_admin_cache(admin.tenant_id, "dashboard")
    if cached:
        return DashboardMetrics(**cached)

    tz = pytz.timezone(settings.calendar_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    async with get_session_context() as session:
        # Single query: today counts + revenue using conditional aggregation
        today_agg = (await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(Cita.estado == EstadoCita.COMPLETADA).label("completadas"),
                func.coalesce(
                    func.sum(Cita.precio_total).filter(
                        Cita.estado.in_([EstadoCita.COMPLETADA, EstadoCita.CONFIRMADA])
                    ),
                    0.0,
                ).label("ingresos"),
            )
            .where(Cita.tenant_id == admin.tenant_id, Cita.inicio >= today_start, Cita.inicio < today_end)
        )).one()

        citas_hoy = today_agg.total
        citas_completadas = today_agg.completadas
        ingresos_hoy = float(today_agg.ingresos)

        # Pending (future)
        citas_pendientes = (await session.execute(
            select(func.count()).select_from(Cita)
            .where(
                Cita.tenant_id == admin.tenant_id,
                Cita.estado.in_([EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA]),
                Cita.inicio >= now,
            )
        )).scalar()

        # Active services + consultants
        total_servicios = (await session.execute(
            select(func.count()).select_from(ServicioBelleza)
            .where(ServicioBelleza.tenant_id == admin.tenant_id, ServicioBelleza.activo.is_(True))
        )).scalar()

        total_estilistas = (await session.execute(
            select(func.count()).select_from(Estilista)
            .where(Estilista.tenant_id == admin.tenant_id, Estilista.activo.is_(True))
        )).scalar()

        # Bot stats today
        stats_result = await session.execute(
            select(EstadisticasBot)
            .where(EstadisticasBot.tenant_id == admin.tenant_id, EstadisticasBot.fecha >= today_start, EstadisticasBot.fecha < today_end)
            .order_by(EstadisticasBot.fecha.desc())
            .limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        mensajes_hoy = stats.mensajes_recibidos if stats else 0
        errores_hoy = stats.errores if stats else 0

        # Monthly usage summary (current calendar month)
        month_start = today_start.replace(day=1)
        usage_result = await session.execute(
            select(
                func.coalesce(func.sum(EstadisticasBot.mensajes_recibidos), 0),
                func.coalesce(func.sum(EstadisticasBot.mensajes_audio), 0),
                func.coalesce(func.sum(EstadisticasBot.mensajes_imagen), 0),
                func.coalesce(func.sum(EstadisticasBot.tokens_openai_aprox), 0),
            ).where(
                EstadisticasBot.tenant_id == admin.tenant_id,
                EstadisticasBot.fecha >= month_start,
            )
        )
        usage_row = usage_result.one()
        uso = UsageResumen(
            mensajes_mes=usage_row[0],
            mensajes_audio_mes=usage_row[1],
            mensajes_imagen_mes=usage_row[2],
            tokens_openai_mes=usage_row[3],
            usuarios_unicos_hoy=stats.usuarios_unicos if stats else 0,
        )

        # CRM Lead metrics
        total_leads = (await session.execute(
            select(func.count()).select_from(Lead)
            .where(Lead.tenant_id == admin.tenant_id, Lead.activo.is_(True))
        )).scalar()

        leads_nuevos_hoy = (await session.execute(
            select(func.count()).select_from(Lead)
            .where(Lead.tenant_id == admin.tenant_id, Lead.created_at >= today_start, Lead.created_at < today_end)
        )).scalar()

        # In pipeline = active leads NOT in cerrado_ganado / cerrado_perdido
        leads_en_pipeline = (await session.execute(
            select(func.count()).select_from(Lead)
            .where(
                Lead.tenant_id == admin.tenant_id,
                Lead.activo.is_(True),
                Lead.etapa.notin_(["cerrado_ganado", "cerrado_perdido"]),
            )
        )).scalar()

        # Overdue follow-ups
        seguimientos_pendientes = (await session.execute(
            select(func.count()).select_from(Lead)
            .where(
                Lead.tenant_id == admin.tenant_id,
                Lead.activo.is_(True),
                Lead.proximo_seguimiento.isnot(None),
                Lead.proximo_seguimiento <= now,
            )
        )).scalar()

        # Weekly chart — last 7 days
        week_start = today_start - timedelta(days=6)
        week_result = await session.execute(
            select(
                func.date_trunc("day", Cita.inicio).label("fecha"),
                func.count().label("cantidad"),
            )
            .where(Cita.tenant_id == admin.tenant_id, Cita.inicio >= week_start, Cita.inicio < today_end)
            .group_by("fecha")
            .order_by("fecha")
        )
        citas_semana = [
            {"fecha": row.fecha.isoformat(), "cantidad": row.cantidad}
            for row in week_result.all()
        ]

        # Recent appointments
        recientes_result = await session.execute(
            select(Cita)
            .where(Cita.tenant_id == admin.tenant_id)
            .order_by(Cita.created_at.desc())
            .limit(5)
        )
        citas_recientes = [
            {
                "id": c.id,
                "nombre_cliente": c.nombre_cliente,
                "inicio": c.inicio.isoformat(),
                "estado": c.estado.value,
                "servicios": c.servicios,
                "precio_total": c.precio_total,
            }
            for c in recientes_result.scalars().all()
        ]

    result = DashboardMetrics(
        citas_hoy=citas_hoy,
        citas_pendientes=citas_pendientes,
        citas_completadas_hoy=citas_completadas,
        ingresos_hoy=ingresos_hoy,
        total_servicios=total_servicios,
        total_estilistas=total_estilistas,
        mensajes_hoy=mensajes_hoy,
        errores_hoy=errores_hoy,
        total_leads=total_leads,
        leads_nuevos_hoy=leads_nuevos_hoy,
        leads_en_pipeline=leads_en_pipeline,
        seguimientos_pendientes=seguimientos_pendientes,
        uso=uso,
        citas_semana=citas_semana,
        citas_recientes=citas_recientes,
    )

    # Cache for 60s
    await redis_cache.set_admin_cache(admin.tenant_id, "dashboard", result.model_dump(), DASHBOARD_CACHE_TTL)

    return result
