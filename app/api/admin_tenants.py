"""
Admin CRUD endpoints for tenant management (SuperAdmin only).
"""

import secrets
from datetime import datetime, time, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.database import get_session_context
from app.models.models import (
    AdminUser,
    ConversacionChatwoot,
    DiaSemana,
    Estilista,
    EstadisticasBot,
    HorarioEstilista,
    InformacionGeneral,
    KeywordHumano,
    PlanTenant,
    ServicioBelleza,
    Tenant,
)
from app.utils.admin_deps import require_superadmin_role

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["Admin Tenants"])


# ── Schemas ────────────────────────────────────────────────


class TenantResponse(BaseModel):
    id: int
    nombre: str
    slug: str
    plan: str
    chatwoot_account_id: Optional[int] = None
    chatwoot_inbox_id: Optional[int] = None
    google_calendar_id: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    max_conversations_per_day: int
    timezone: str
    activo: bool
    trial_ends_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None
    last_payment_at: Optional[datetime] = None
    payment_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantCreate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    plan: str = Field(default="trial")
    chatwoot_account_id: Optional[int] = None
    chatwoot_inbox_id: Optional[int] = None
    chatwoot_api_token: Optional[str] = None
    google_calendar_id: Optional[str] = None
    owner_phone: Optional[str] = Field(default=None, max_length=20)
    owner_email: Optional[str] = Field(default=None, max_length=150)
    system_prompt_override: Optional[str] = Field(default=None, max_length=10000)
    max_conversations_per_day: int = Field(default=100, ge=1)
    timezone: str = Field(default="America/Mexico_City", max_length=50)
    trial_ends_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None


class SeedDemoResponse(BaseModel):
    message: str
    servicios_creados: int
    estilistas_creados: int
    info_creada: bool
    keywords_creados: int


class TenantUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, max_length=200)
    slug: Optional[str] = Field(default=None, max_length=100, pattern=r"^[a-z0-9\-]+$")
    plan: Optional[str] = None
    chatwoot_account_id: Optional[int] = None
    chatwoot_inbox_id: Optional[int] = None
    chatwoot_api_token: Optional[str] = None
    google_calendar_id: Optional[str] = None
    owner_phone: Optional[str] = Field(default=None, max_length=20)
    owner_email: Optional[str] = Field(default=None, max_length=150)
    system_prompt_override: Optional[str] = Field(default=None, max_length=10000)
    max_conversations_per_day: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = Field(default=None, max_length=50)
    activo: Optional[bool] = None
    trial_ends_at: Optional[datetime] = None
    subscription_expires_at: Optional[datetime] = None


# ── Endpoints ──────────────────────────────────────────────


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    activo: Optional[bool] = None,
    admin: AdminUser = Depends(require_superadmin_role),
):
    async with get_session_context() as session:
        q = select(Tenant)
        if activo is not None:
            q = q.where(Tenant.activo == activo)
        q = q.order_by(Tenant.nombre)
        result = await session.execute(q)
        return result.scalars().all()


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    admin: AdminUser = Depends(require_superadmin_role),
):
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")
        return tenant


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    admin: AdminUser = Depends(require_superadmin_role),
):
    async with get_session_context() as session:
        # Check slug uniqueness
        exists = await session.execute(
            select(func.count()).where(Tenant.slug == body.slug)
        )
        if exists.scalar():
            raise HTTPException(status_code=409, detail="Ya existe un tenant con ese slug")

        data = body.model_dump()
        # Validate plan
        try:
            data["plan"] = PlanTenant(data["plan"])
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Plan invalido. Opciones: {[p.value for p in PlanTenant]}",
            )

        # Auto-generate webhook_token if not provided
        if not data.get("webhook_token"):
            data["webhook_token"] = secrets.token_urlsafe(32)

        tenant = Tenant(**data)
        session.add(tenant)
        await session.flush()
        await session.refresh(tenant)
        return tenant


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    body: TenantUpdate,
    admin: AdminUser = Depends(require_superadmin_role),
):
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")

        update_data = body.model_dump(exclude_unset=True)

        # Check slug uniqueness if changing
        if "slug" in update_data and update_data["slug"] != tenant.slug:
            dup = await session.execute(
                select(func.count()).where(
                    Tenant.slug == update_data["slug"],
                    Tenant.id != tenant_id,
                )
            )
            if dup.scalar():
                raise HTTPException(status_code=409, detail="Ya existe un tenant con ese slug")

        # Validate plan if changing
        if "plan" in update_data:
            try:
                update_data["plan"] = PlanTenant(update_data["plan"])
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Plan invalido. Opciones: {[p.value for p in PlanTenant]}",
                )

        for field, value in update_data.items():
            setattr(tenant, field, value)
        await session.flush()
        await session.refresh(tenant)
        return tenant


@router.post("/{tenant_id}/regenerate-webhook-token", response_model=TenantResponse)
async def regenerate_webhook_token(
    tenant_id: int,
    admin: AdminUser = Depends(require_superadmin_role),
):
    """Regenerate the webhook token for a tenant."""
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")
        tenant.webhook_token = secrets.token_urlsafe(32)
        await session.flush()
        await session.refresh(tenant)
        return tenant


@router.post("/{tenant_id}/seed-demo", response_model=SeedDemoResponse)
async def seed_demo_data(
    tenant_id: int,
    admin: AdminUser = Depends(require_superadmin_role),
):
    """Seed realistic beauty-salon demo data for a tenant."""
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")

        # Guard: don't seed if tenant already has data
        count = await session.execute(
            select(func.count()).select_from(ServicioBelleza).where(
                ServicioBelleza.tenant_id == tenant_id
            )
        )
        if count.scalar():
            raise HTTPException(
                status_code=409,
                detail="Este tenant ya tiene datos cargados",
            )

        # ── Services ──────────────────────────────────────────
        services_data = [
            ("Corte de cabello dama", "Corte personalizado con lavado y secado", 350, 45),
            ("Corte de cabello caballero", "Corte clásico o moderno con lavado", 200, 30),
            ("Tinte completo", "Aplicación de color completo con productos profesionales", 800, 120),
            ("Mechas / Balayage", "Técnica de iluminación parcial o total", 1200, 150),
            ("Manicure y Pedicure", "Tratamiento completo de uñas manos y pies", 450, 60),
            ("Tratamiento capilar", "Hidratación profunda o keratina", 600, 90),
        ]
        stylist_names = ["Ana Martínez", "Carlos López", "María García"]

        services = []
        for nombre, desc, precio, dur in services_data:
            svc = ServicioBelleza(
                servicio=nombre,
                descripcion=desc,
                precio=precio,
                duracion_minutos=dur,
                estilistas_disponibles=stylist_names,
                tenant_id=tenant_id,
            )
            session.add(svc)
            services.append(svc)

        # ── Stylists + schedules ──────────────────────────────
        stylists_config = [
            {
                "nombre": "Ana Martínez",
                "telefono": "55 1111 2222",
                "email": "ana@ejemplo.com",
                "especialidades": ["Colorimetría", "Cortes de dama", "Tratamientos capilares"],
                "dias": [DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES,
                         DiaSemana.JUEVES, DiaSemana.VIERNES, DiaSemana.SABADO],
                "hora_inicio": time(9, 0),
                "hora_fin": time(18, 0),
            },
            {
                "nombre": "Carlos López",
                "telefono": "55 3333 4444",
                "email": "carlos@ejemplo.com",
                "especialidades": ["Cortes de caballero", "Barbería", "Cortes de dama"],
                "dias": [DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES,
                         DiaSemana.JUEVES, DiaSemana.VIERNES],
                "hora_inicio": time(10, 0),
                "hora_fin": time(19, 0),
            },
            {
                "nombre": "María García",
                "telefono": "55 5555 6666",
                "email": "maria@ejemplo.com",
                "especialidades": ["Manicure", "Pedicure", "Uñas acrílicas"],
                "dias": [DiaSemana.LUNES, DiaSemana.MARTES, DiaSemana.MIERCOLES,
                         DiaSemana.JUEVES, DiaSemana.VIERNES, DiaSemana.SABADO],
                "hora_inicio": time(9, 0),
                "hora_fin": time(17, 0),
            },
        ]

        for cfg in stylists_config:
            stylist = Estilista(
                nombre=cfg["nombre"],
                telefono=cfg["telefono"],
                email=cfg["email"],
                especialidades=cfg["especialidades"],
                tenant_id=tenant_id,
            )
            session.add(stylist)
            await session.flush()

            for dia in cfg["dias"]:
                session.add(HorarioEstilista(
                    estilista_id=stylist.id,
                    dia=dia,
                    hora_inicio=cfg["hora_inicio"],
                    hora_fin=cfg["hora_fin"],
                ))

        # ── Business info ─────────────────────────────────────
        session.add(InformacionGeneral(
            nombre_salon=tenant.nombre,
            direccion="Av. Insurgentes Sur 1234, Col. Del Valle, CDMX",
            telefono="55 1234 5678",
            horario="Lunes a Sábado: 9:00 AM - 7:00 PM",
            descripcion=(
                f"{tenant.nombre} es un salón de belleza profesional con los mejores "
                "estilistas y productos de primera calidad. Ofrecemos cortes, "
                "tintes, tratamientos capilares, manicure, pedicure y más."
            ),
            politicas=(
                "• Cancelaciones con mínimo 4 horas de anticipación\n"
                "• Llegadas con más de 15 min de retraso podrán ser reprogramadas\n"
                "• Precios pueden variar según largo y tipo de cabello"
            ),
            redes_sociales={
                "instagram": f"@{tenant.slug}",
                "facebook": tenant.nombre,
            },
            tenant_id=tenant_id,
        ))

        # ── Human-handoff keywords ────────────────────────────
        keywords = [
            "hablar con humano", "hablar con persona", "agente humano",
            "quiero hablar con alguien", "operador", "persona real",
            "atencion al cliente", "atención al cliente", "queja",
            "reclamación", "reclamacion", "problema urgente", "emergencia",
        ]
        for kw in keywords:
            session.add(KeywordHumano(keyword=kw, tenant_id=tenant_id))

    # Invalidate caches outside the session (auto-committed)
    from app.services.redis_cache import redis_cache

    await redis_cache.invalidate_services(tenant_id)
    await redis_cache.invalidate_stylists(tenant_id)
    await redis_cache.invalidate_info(tenant_id)
    await redis_cache.invalidate_keywords(tenant_id)

    logger.info("Demo data seeded for tenant", tenant_id=tenant_id, tenant_name=tenant.nombre)

    return SeedDemoResponse(
        message="Datos demo de salón de belleza cargados exitosamente",
        servicios_creados=len(services),
        estilistas_creados=len(stylists_config),
        info_creada=True,
        keywords_creados=len(keywords),
    )


# ── Billing ───────────────────────────────────────────────


class ConfirmPaymentRequest(BaseModel):
    months: int = Field(default=1, ge=1, le=12)
    notes: Optional[str] = Field(default=None, max_length=500)


class ConfirmPaymentResponse(BaseModel):
    message: str
    tenant_id: int
    plan: str
    subscription_expires_at: datetime
    last_payment_at: datetime

    class Config:
        from_attributes = True


@router.post("/{tenant_id}/confirm-payment", response_model=ConfirmPaymentResponse)
async def confirm_payment(
    tenant_id: int,
    body: ConfirmPaymentRequest,
    admin: AdminUser = Depends(require_superadmin_role),
):
    """Confirm payment for a tenant and extend subscription by N months."""
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")

        now = datetime.now(timezone.utc)

        # Extend from current expiry if still in future, otherwise from now
        if tenant.subscription_expires_at and tenant.subscription_expires_at > now:
            base_date = tenant.subscription_expires_at
        else:
            base_date = now

        # Add N months (approximate: 30 days per month)
        new_expiry = base_date + timedelta(days=30 * body.months)

        tenant.subscription_expires_at = new_expiry
        tenant.last_payment_at = now
        tenant.plan = PlanTenant.ACTIVE
        tenant.activo = True

        if body.notes:
            existing = tenant.payment_notes or ""
            date_str = now.strftime("%Y-%m-%d")
            entry = f"[{date_str}] +{body.months}m — {body.notes}"
            tenant.payment_notes = f"{entry}\n{existing}".strip() if existing else entry

        await session.flush()
        await session.refresh(tenant)

        logger.info(
            "Payment confirmed",
            tenant_id=tenant.id,
            months=body.months,
            new_expiry=new_expiry.isoformat(),
        )

        return ConfirmPaymentResponse(
            message=f"Pago confirmado. Suscripción extendida hasta {new_expiry.strftime('%Y-%m-%d')}",
            tenant_id=tenant.id,
            plan=tenant.plan.value,
            subscription_expires_at=tenant.subscription_expires_at,
            last_payment_at=tenant.last_payment_at,
        )


# ── Usage metrics ─────────────────────────────────────────────


class DailyUsageDetail(BaseModel):
    fecha: str
    mensajes_recibidos: int
    mensajes_respondidos: int
    mensajes_audio: int
    mensajes_imagen: int
    usuarios_unicos: int
    tokens_openai_aprox: int
    citas_creadas: int
    errores: int


class TenantUsageResponse(BaseModel):
    tenant_id: int
    tenant_nombre: str
    periodo: str
    total_mensajes_recibidos: int
    total_mensajes_respondidos: int
    total_mensajes_audio: int
    total_mensajes_imagen: int
    total_tokens_openai_aprox: int
    total_citas_creadas: int
    total_transferencias_humano: int
    total_errores: int
    promedio_respuesta_ms: Optional[float]
    conversaciones_activas: int
    detalle_diario: list[DailyUsageDetail]


@router.get("/{tenant_id}/usage", response_model=TenantUsageResponse)
async def get_tenant_usage(
    tenant_id: int,
    dias: int = Query(30, ge=1, le=90, description="Días hacia atrás a consultar"),
    admin: AdminUser = Depends(require_superadmin_role),
):
    """Get usage metrics for a specific tenant over the last N days."""
    async with get_session_context() as session:
        tenant = await session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant no encontrado")

        desde = datetime.now(timezone.utc) - timedelta(days=dias)

        # Get daily stats for the period
        stats_result = await session.execute(
            select(EstadisticasBot)
            .where(
                EstadisticasBot.tenant_id == tenant_id,
                EstadisticasBot.fecha >= desde,
            )
            .order_by(EstadisticasBot.fecha)
        )
        stats_rows = stats_result.scalars().all()

        # Get active conversation count
        conv_result = await session.execute(
            select(func.count()).where(
                ConversacionChatwoot.tenant_id == tenant_id,
                ConversacionChatwoot.bot_activo == True,
            )
        )
        active_convs = conv_result.scalar() or 0

    # Aggregate totals
    total_recibidos = sum(s.mensajes_recibidos for s in stats_rows)
    total_respondidos = sum(s.mensajes_respondidos for s in stats_rows)
    total_audio = sum(s.mensajes_audio for s in stats_rows)
    total_imagen = sum(s.mensajes_imagen for s in stats_rows)
    total_tokens = sum(s.tokens_openai_aprox for s in stats_rows)
    total_citas = sum(s.citas_creadas for s in stats_rows)
    total_handoffs = sum(s.transferencias_humano for s in stats_rows)
    total_errores = sum(s.errores for s in stats_rows)

    # Weighted average response time
    weighted_sum = sum(
        (s.tiempo_respuesta_promedio_ms or 0) * s.mensajes_respondidos
        for s in stats_rows
    )
    promedio_ms = (
        round(weighted_sum / total_respondidos, 1)
        if total_respondidos > 0
        else None
    )

    detalle = [
        DailyUsageDetail(
            fecha=s.fecha.strftime("%Y-%m-%d"),
            mensajes_recibidos=s.mensajes_recibidos,
            mensajes_respondidos=s.mensajes_respondidos,
            mensajes_audio=s.mensajes_audio,
            mensajes_imagen=s.mensajes_imagen,
            usuarios_unicos=s.usuarios_unicos,
            tokens_openai_aprox=s.tokens_openai_aprox,
            citas_creadas=s.citas_creadas,
            errores=s.errores,
        )
        for s in stats_rows
    ]

    return TenantUsageResponse(
        tenant_id=tenant.id,
        tenant_nombre=tenant.nombre,
        periodo=f"Últimos {dias} días",
        total_mensajes_recibidos=total_recibidos,
        total_mensajes_respondidos=total_respondidos,
        total_mensajes_audio=total_audio,
        total_mensajes_imagen=total_imagen,
        total_tokens_openai_aprox=total_tokens,
        total_citas_creadas=total_citas,
        total_transferencias_humano=total_handoffs,
        total_errores=total_errores,
        promedio_respuesta_ms=promedio_ms,
        conversaciones_activas=active_convs,
        detalle_diario=detalle,
    )


# ── All-tenants usage comparison ──────────────────────────────


class TenantUsageSummary(BaseModel):
    tenant_id: int
    nombre: str
    plan: str
    activo: bool
    mensajes_mes: int
    tokens_mes: int
    citas_mes: int
    errores_mes: int


@router.get("/usage/overview", response_model=list[TenantUsageSummary])
async def get_all_tenants_usage(
    admin: AdminUser = Depends(require_superadmin_role),
):
    """Compare usage across all tenants for the current calendar month."""
    async with get_session_context() as session:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get all tenants
        tenants_result = await session.execute(select(Tenant).order_by(Tenant.id))
        tenants = tenants_result.scalars().all()

        # Aggregate stats for current month per tenant
        stats_result = await session.execute(
            select(
                EstadisticasBot.tenant_id,
                func.coalesce(func.sum(EstadisticasBot.mensajes_recibidos), 0).label("mensajes"),
                func.coalesce(func.sum(EstadisticasBot.tokens_openai_aprox), 0).label("tokens"),
                func.coalesce(func.sum(EstadisticasBot.citas_creadas), 0).label("citas"),
                func.coalesce(func.sum(EstadisticasBot.errores), 0).label("errores"),
            )
            .where(EstadisticasBot.fecha >= month_start)
            .group_by(EstadisticasBot.tenant_id)
        )
        usage_by_tenant = {row.tenant_id: row for row in stats_result.all()}

    summaries = []
    for t in tenants:
        usage = usage_by_tenant.get(t.id)
        summaries.append(TenantUsageSummary(
            tenant_id=t.id,
            nombre=t.nombre,
            plan=t.plan.value,
            activo=t.activo,
            mensajes_mes=usage.mensajes if usage else 0,
            tokens_mes=usage.tokens if usage else 0,
            citas_mes=usage.citas if usage else 0,
            errores_mes=usage.errores if usage else 0,
        ))

    return summaries
