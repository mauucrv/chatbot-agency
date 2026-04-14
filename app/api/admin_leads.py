"""
Admin CRUD endpoints for CRM leads.
"""

from datetime import datetime
from typing import Optional

import pytz
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update

from app.agent.tools import escape_ilike
from app.config import settings
from app.database import get_session_context
from app.models.models import AdminUser, Cita, ConversacionChatwoot, EtapaLead, Lead
from app.schemas.schemas import AppointmentResponse, LeadCreate, LeadResponse, LeadUpdate
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

TZ = pytz.timezone(settings.calendar_timezone)

router = APIRouter(prefix="/leads", tags=["Admin CRM Leads"])


class PaginatedLeads(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


class PipelineStage(BaseModel):
    etapa: str
    cantidad: int
    valor_total: float


# ── List / Search ─────────────────────────────────────────────

@router.get("", response_model=PaginatedLeads)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    busqueda: Optional[str] = None,
    etapa: Optional[str] = None,
    origen: Optional[str] = None,
    activo: Optional[bool] = None,
    seguimiento_pendiente: Optional[bool] = None,
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        q = select(Lead).where(Lead.tenant_id == admin.tenant_id)
        count_q = select(func.count()).select_from(Lead).where(Lead.tenant_id == admin.tenant_id)

        if activo is not None:
            q = q.where(Lead.activo == activo)
            count_q = count_q.where(Lead.activo == activo)

        if etapa:
            q = q.where(Lead.etapa == etapa)
            count_q = count_q.where(Lead.etapa == etapa)

        if origen:
            q = q.where(Lead.origen == origen)
            count_q = count_q.where(Lead.origen == origen)

        if busqueda:
            pattern = f"%{escape_ilike(busqueda)}%"
            search_filter = (
                Lead.nombre.ilike(pattern)
                | Lead.telefono.ilike(pattern)
                | Lead.empresa.ilike(pattern)
            )
            q = q.where(search_filter)
            count_q = count_q.where(search_filter)

        if seguimiento_pendiente:
            now = datetime.now(TZ)
            q = q.where(Lead.proximo_seguimiento <= now, Lead.activo.is_(True))
            count_q = count_q.where(Lead.proximo_seguimiento <= now, Lead.activo.is_(True))

        total = (await session.execute(count_q)).scalar()

        q = q.order_by(Lead.updated_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = result.scalars().all()

        return PaginatedLeads(items=items, total=total, page=page, page_size=page_size)


# ── Pipeline Summary ─────────────────────────────────────────

@router.get("/pipeline/summary", response_model=list[PipelineStage])
async def pipeline_summary(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(
                Lead.etapa,
                func.count().label("cantidad"),
                func.coalesce(func.sum(Lead.valor_estimado), 0.0).label("valor_total"),
            )
            .where(Lead.activo.is_(True), Lead.tenant_id == admin.tenant_id)
            .group_by(Lead.etapa)
        )
        rows = result.all()

        # Return all stages, even if 0
        stage_data = {r.etapa: {"cantidad": r.cantidad, "valor_total": r.valor_total} for r in rows}
        stages = []
        for etapa in EtapaLead:
            data = stage_data.get(etapa.value, {"cantidad": 0, "valor_total": 0.0})
            stages.append(PipelineStage(etapa=etapa.value, **data))
        return stages


# ── Pending Follow-ups ────────────────────────────────────────

@router.get("/seguimiento/pendientes", response_model=list[LeadResponse])
async def pending_followups(admin: AdminUser = Depends(get_current_admin)):
    now = datetime.now(TZ)
    async with get_session_context() as session:
        result = await session.execute(
            select(Lead)
            .where(
                Lead.activo.is_(True),
                Lead.proximo_seguimiento.isnot(None),
                Lead.proximo_seguimiento <= now,
                Lead.tenant_id == admin.tenant_id,
            )
            .order_by(Lead.proximo_seguimiento)
            .limit(50)
        )
        return result.scalars().all()


# ── Detail ────────────────────────────────────────────────────

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")
        return lead


@router.get("/{lead_id}/citas", response_model=list[AppointmentResponse])
async def get_lead_citas(lead_id: int, admin: AdminUser = Depends(get_current_admin)):
    """Get appointments linked to this lead by phone number."""
    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")

        result = await session.execute(
            select(Cita)
            .where(Cita.telefono_cliente == lead.telefono, Cita.tenant_id == admin.tenant_id)
            .order_by(Cita.inicio.desc())
            .limit(50)
        )
        return result.scalars().all()


@router.get("/{lead_id}/conversacion")
async def get_lead_conversacion(lead_id: int, admin: AdminUser = Depends(get_current_admin)):
    """Get linked Chatwoot conversation data."""
    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")

        if not lead.chatwoot_conversation_id:
            return None

        result = await session.execute(
            select(ConversacionChatwoot)
            .where(
                ConversacionChatwoot.chatwoot_conversation_id == lead.chatwoot_conversation_id,
                ConversacionChatwoot.tenant_id == admin.tenant_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return None

        return {
            "conversation_id": conv.chatwoot_conversation_id,
            "contact_id": conv.chatwoot_contact_id,
            "bot_activo": conv.bot_activo,
            "ultimo_mensaje_at": conv.ultimo_mensaje_at,
        }


# ── Create / Update / Delete ─────────────────────────────────

@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(body: LeadCreate, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        exists = await session.execute(
            select(func.count()).where(
                Lead.telefono == body.telefono,
                Lead.tenant_id == admin.tenant_id,
            )
        )
        if exists.scalar():
            raise HTTPException(status_code=409, detail="Ya existe un lead con ese telefono")

        lead = Lead(**body.model_dump(), tenant_id=admin.tenant_id)
        session.add(lead)
        await session.flush()
        await session.refresh(lead)
        return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: int,
    body: LeadUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")

        update_data = body.model_dump(exclude_unset=True)

        if "telefono" in update_data and update_data["telefono"] != lead.telefono:
            dup = await session.execute(
                select(func.count()).where(
                    Lead.telefono == update_data["telefono"],
                    Lead.id != lead_id,
                    Lead.tenant_id == admin.tenant_id,
                )
            )
            if dup.scalar():
                raise HTTPException(status_code=409, detail="Ya existe un lead con ese telefono")

        for field, value in update_data.items():
            setattr(lead, field, value)
        await session.flush()
        await session.refresh(lead)
        return lead


@router.patch("/{lead_id}/etapa", response_model=LeadResponse)
async def change_lead_stage(
    lead_id: int,
    etapa: str = Query(...),
    admin: AdminUser = Depends(require_admin_role),
):
    """Quick stage change for pipeline management."""
    valid_stages = [e.value for e in EtapaLead]
    if etapa not in valid_stages:
        raise HTTPException(status_code=400, detail=f"Etapa invalida. Opciones: {valid_stages}")

    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")

        lead.etapa = etapa
        await session.flush()
        await session.refresh(lead)
        return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(lead_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        lead = await session.get(Lead, lead_id)
        check_tenant_access(lead, admin, "Lead no encontrado")
        await session.delete(lead)
