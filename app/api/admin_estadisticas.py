"""
Admin statistics endpoints — trends and aggregated data, cached in Redis.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.database import get_session_context
from app.models.models import AdminUser, Cita, EstadisticasBot, EstadoCita, Estilista
from app.schemas.schemas import DailyStatistics
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import get_current_admin

router = APIRouter(prefix="/estadisticas", tags=["Admin Estadisticas"])

STATS_CACHE_TTL = 120  # seconds


class StatsOverview(BaseModel):
    daily_stats: list[DailyStatistics]
    servicios_populares: list[dict]
    citas_por_estado: list[dict]
    citas_por_estilista: list[dict]
    tasa_completadas: float
    tasa_canceladas: float


@router.get("/overview", response_model=StatsOverview)
async def get_stats_overview(
    fecha_desde: datetime = Query(...),
    fecha_hasta: datetime = Query(...),
    admin: AdminUser = Depends(get_current_admin),
):
    # Cache key based on date range
    cache_key = f"stats_overview:{fecha_desde.date()}:{fecha_hasta.date()}"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return StatsOverview(**cached)

    async with get_session_context() as session:
        # Daily bot stats
        stats_result = await session.execute(
            select(EstadisticasBot)
            .where(
                EstadisticasBot.tenant_id == admin.tenant_id,
                EstadisticasBot.fecha >= fecha_desde,
                EstadisticasBot.fecha <= fecha_hasta,
            )
            .order_by(EstadisticasBot.fecha)
        )
        daily_stats = [
            DailyStatistics(
                fecha=s.fecha,
                mensajes_recibidos=s.mensajes_recibidos,
                mensajes_respondidos=s.mensajes_respondidos,
                mensajes_audio=s.mensajes_audio,
                mensajes_imagen=s.mensajes_imagen,
                usuarios_unicos=s.usuarios_unicos,
                tokens_openai_aprox=s.tokens_openai_aprox,
                citas_creadas=s.citas_creadas,
                citas_modificadas=s.citas_modificadas,
                citas_canceladas=s.citas_canceladas,
                transferencias_humano=s.transferencias_humano,
                errores=s.errores,
                tiempo_respuesta_promedio_ms=s.tiempo_respuesta_promedio_ms,
            )
            for s in stats_result.scalars().all()
        ]

        # Popular services — unnest JSON in SQL instead of loading all into Python
        svc_result = await session.execute(
            text("""
                SELECT elem AS servicio, COUNT(*) AS cantidad
                FROM citas c, jsonb_array_elements_text(c.servicios::jsonb) AS elem
                WHERE c.inicio >= :desde AND c.inicio <= :hasta
                  AND c.tenant_id = :tenant_id
                GROUP BY elem
                ORDER BY cantidad DESC
                LIMIT 10
            """),
            {"desde": fecha_desde, "hasta": fecha_hasta, "tenant_id": admin.tenant_id},
        )
        servicios_populares = [
            {"servicio": row.servicio, "cantidad": row.cantidad}
            for row in svc_result.all()
        ]

        # Appointments by status
        status_result = await session.execute(
            select(Cita.estado, func.count())
            .where(Cita.tenant_id == admin.tenant_id, Cita.inicio >= fecha_desde, Cita.inicio <= fecha_hasta)
            .group_by(Cita.estado)
        )
        citas_por_estado = [
            {"estado": row[0].value, "cantidad": row[1]}
            for row in status_result.all()
        ]

        # Appointments by stylist
        stylist_result = await session.execute(
            select(Estilista.nombre, func.count())
            .join(Cita, Cita.estilista_id == Estilista.id)
            .where(Cita.tenant_id == admin.tenant_id, Cita.inicio >= fecha_desde, Cita.inicio <= fecha_hasta)
            .group_by(Estilista.nombre)
            .order_by(func.count().desc())
        )
        citas_por_estilista = [
            {"estilista": row[0], "cantidad": row[1]}
            for row in stylist_result.all()
        ]

        # Completion/cancellation rates
        total_citas = sum(c["cantidad"] for c in citas_por_estado) or 1
        completadas = next(
            (c["cantidad"] for c in citas_por_estado if c["estado"] == "completada"), 0
        )
        canceladas = next(
            (c["cantidad"] for c in citas_por_estado if c["estado"] == "cancelada"), 0
        )

    result = StatsOverview(
        daily_stats=daily_stats,
        servicios_populares=servicios_populares,
        citas_por_estado=citas_por_estado,
        citas_por_estilista=citas_por_estilista,
        tasa_completadas=round(completadas / total_citas * 100, 1),
        tasa_canceladas=round(canceladas / total_citas * 100, 1),
    )

    await redis_cache.set_admin_cache(admin.tenant_id, cache_key, result.model_dump(), STATS_CACHE_TTL)

    return result


class TrendPoint(BaseModel):
    fecha: str
    valor: float


@router.get("/tendencia-citas", response_model=list[TrendPoint])
async def appointment_trend(
    dias: int = Query(30, ge=7, le=90),
    admin: AdminUser = Depends(get_current_admin),
):
    """Daily appointment count for the last N days."""
    cache_key = f"trend:{dias}"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return [TrendPoint(**p) for p in cached]

    desde = datetime.utcnow() - timedelta(days=dias)
    async with get_session_context() as session:
        result = await session.execute(
            select(
                func.date_trunc("day", Cita.inicio).label("fecha"),
                func.count().label("valor"),
            )
            .where(Cita.tenant_id == admin.tenant_id, Cita.inicio >= desde)
            .group_by("fecha")
            .order_by("fecha")
        )
        points = [
            TrendPoint(fecha=row.fecha.isoformat(), valor=row.valor)
            for row in result.all()
        ]

    await redis_cache.set_admin_cache(
        admin.tenant_id, cache_key, [p.model_dump() for p in points], STATS_CACHE_TTL
    )

    return points
