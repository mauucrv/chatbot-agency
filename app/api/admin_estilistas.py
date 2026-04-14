"""
Admin CRUD endpoints for stylists + schedules.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_session_context
from app.models.models import AdminUser, DiaSemana, Estilista, HorarioEstilista
from app.schemas.schemas import (
    StylistCreate,
    StylistResponse,
    StylistScheduleBase,
    StylistScheduleResponse,
    StylistUpdate,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/estilistas", tags=["Admin Estilistas"])


@router.get("", response_model=list[StylistResponse])
async def list_stylists(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Estilista)
            .options(selectinload(Estilista.horarios))
            .where(Estilista.tenant_id == admin.tenant_id)
            .order_by(Estilista.nombre)
        )
        return result.scalars().all()


@router.get("/{stylist_id}", response_model=StylistResponse)
async def get_stylist(stylist_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Estilista)
            .options(selectinload(Estilista.horarios))
            .where(Estilista.id == stylist_id)
            .where(Estilista.tenant_id == admin.tenant_id)
        )
        stylist = result.scalar_one_or_none()
        if not stylist:
            raise HTTPException(status_code=404, detail="Estilista no encontrado")
        return stylist


@router.post("", response_model=StylistResponse, status_code=status.HTTP_201_CREATED)
async def create_stylist(
    body: StylistCreate, admin: AdminUser = Depends(require_admin_role)
):
    async with get_session_context() as session:
        stylist = Estilista(**body.model_dump(), tenant_id=admin.tenant_id)
        session.add(stylist)
        await session.flush()
        result = await session.execute(
            select(Estilista)
            .options(selectinload(Estilista.horarios))
            .where(Estilista.id == stylist.id)
            .where(Estilista.tenant_id == admin.tenant_id)
        )
        stylist = result.scalar_one()
        await redis_cache.invalidate_stylists(admin.tenant_id)
        return stylist


@router.put("/{stylist_id}", response_model=StylistResponse)
async def update_stylist(
    stylist_id: int,
    body: StylistUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        result = await session.execute(
            select(Estilista)
            .options(selectinload(Estilista.horarios))
            .where(Estilista.id == stylist_id)
            .where(Estilista.tenant_id == admin.tenant_id)
        )
        stylist = result.scalar_one_or_none()
        if not stylist:
            raise HTTPException(status_code=404, detail="Estilista no encontrado")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(stylist, field, value)
        await session.flush()
        await session.refresh(stylist)
        await redis_cache.invalidate_stylists(admin.tenant_id)
        return stylist


@router.delete("/{stylist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stylist(stylist_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        stylist = await session.get(Estilista, stylist_id)
        check_tenant_access(stylist, admin, "Estilista no encontrado")
        await session.delete(stylist)
        await redis_cache.invalidate_stylists(admin.tenant_id)


# ── Schedules ──────────────────────────────────────────────


@router.put("/{stylist_id}/horarios", response_model=list[StylistScheduleResponse])
async def replace_schedules(
    stylist_id: int,
    horarios: list[StylistScheduleBase],
    admin: AdminUser = Depends(require_admin_role),
):
    """Replace all schedules for a stylist (delete + recreate)."""
    async with get_session_context() as session:
        result = await session.execute(
            select(Estilista)
            .options(selectinload(Estilista.horarios))
            .where(Estilista.id == stylist_id)
            .where(Estilista.tenant_id == admin.tenant_id)
        )
        stylist = result.scalar_one_or_none()
        if not stylist:
            raise HTTPException(status_code=404, detail="Estilista no encontrado")
        for h in list(stylist.horarios):
            await session.delete(h)
        await session.flush()
        new_horarios = []
        for h in horarios:
            horario = HorarioEstilista(
                estilista_id=stylist_id,
                dia=DiaSemana(h.dia),
                hora_inicio=h.hora_inicio,
                hora_fin=h.hora_fin,
                activo=True,
            )
            session.add(horario)
            new_horarios.append(horario)
        await session.flush()
        for h in new_horarios:
            await session.refresh(h)
        await redis_cache.invalidate_stylists(admin.tenant_id)
        return new_horarios
