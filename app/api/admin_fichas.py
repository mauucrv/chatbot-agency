"""
Admin CRUD endpoints for client profiles (fichas_clientes).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.agent.tools import escape_ilike
from app.database import get_session_context
from app.models.models import AdminUser, Cita, FichaCliente
from app.schemas.schemas import (
    AppointmentResponse,
    FichaClienteCreate,
    FichaClienteResponse,
    FichaClienteUpdate,
    HistorialEntrada,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/fichas", tags=["Admin Fichas Clientes"])


class PaginatedFichas(BaseModel):
    items: list[FichaClienteResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedFichas)
async def list_fichas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    busqueda: Optional[str] = None,
    activo: Optional[bool] = None,
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        q = select(FichaCliente).where(FichaCliente.tenant_id == admin.tenant_id)
        count_q = select(func.count()).select_from(FichaCliente).where(FichaCliente.tenant_id == admin.tenant_id)

        if activo is not None:
            q = q.where(FichaCliente.activo == activo)
            count_q = count_q.where(FichaCliente.activo == activo)

        if busqueda:
            pattern = f"%{escape_ilike(busqueda)}%"
            search_filter = FichaCliente.nombre.ilike(pattern) | FichaCliente.telefono.ilike(pattern)
            q = q.where(search_filter)
            count_q = count_q.where(search_filter)

        total = (await session.execute(count_q)).scalar()

        q = q.order_by(FichaCliente.nombre)
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = result.scalars().all()

        return PaginatedFichas(items=items, total=total, page=page, page_size=page_size)


@router.get("/{ficha_id}", response_model=FichaClienteResponse)
async def get_ficha(ficha_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")
        return ficha


@router.get("/{ficha_id}/citas", response_model=list[AppointmentResponse])
async def get_ficha_citas(ficha_id: int, admin: AdminUser = Depends(get_current_admin)):
    """Get appointments linked to this client by phone number."""
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")

        result = await session.execute(
            select(Cita)
            .where(Cita.telefono_cliente == ficha.telefono, Cita.tenant_id == admin.tenant_id)
            .order_by(Cita.inicio.desc())
            .limit(50)
        )
        return result.scalars().all()


@router.post("", response_model=FichaClienteResponse, status_code=status.HTTP_201_CREATED)
async def create_ficha(
    body: FichaClienteCreate, admin: AdminUser = Depends(require_admin_role)
):
    async with get_session_context() as session:
        exists = await session.execute(
            select(func.count()).where(
                FichaCliente.telefono == body.telefono,
                FichaCliente.tenant_id == admin.tenant_id,
            )
        )
        if exists.scalar():
            raise HTTPException(status_code=409, detail="Ya existe una ficha con ese telefono")

        ficha = FichaCliente(**body.model_dump(), tenant_id=admin.tenant_id)
        session.add(ficha)
        await session.flush()
        await session.refresh(ficha)
        await redis_cache.invalidate_fichas(admin.tenant_id)
        return ficha


@router.put("/{ficha_id}", response_model=FichaClienteResponse)
async def update_ficha(
    ficha_id: int,
    body: FichaClienteUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")

        update_data = body.model_dump(exclude_unset=True)
        if "telefono" in update_data and update_data["telefono"] != ficha.telefono:
            dup = await session.execute(
                select(func.count()).where(
                    FichaCliente.telefono == update_data["telefono"],
                    FichaCliente.id != ficha_id,
                    FichaCliente.tenant_id == admin.tenant_id,
                )
            )
            if dup.scalar():
                raise HTTPException(status_code=409, detail="Ya existe una ficha con ese telefono")

        for field, value in update_data.items():
            setattr(ficha, field, value)
        await session.flush()
        await session.refresh(ficha)
        await redis_cache.invalidate_fichas(admin.tenant_id)
        return ficha


@router.delete("/{ficha_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ficha(ficha_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")
        await session.delete(ficha)
        await redis_cache.invalidate_fichas(admin.tenant_id)


@router.post("/{ficha_id}/historial-color", response_model=FichaClienteResponse)
async def add_historial_color(
    ficha_id: int,
    entry: HistorialEntrada,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")
        historial = list(ficha.historial_color or [])
        historial.append(entry.model_dump())
        ficha.historial_color = historial
        await session.flush()
        await session.refresh(ficha)
        await redis_cache.invalidate_fichas(admin.tenant_id)
        return ficha


@router.post("/{ficha_id}/historial-tratamientos", response_model=FichaClienteResponse)
async def add_historial_tratamientos(
    ficha_id: int,
    entry: HistorialEntrada,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        ficha = await session.get(FichaCliente, ficha_id)
        check_tenant_access(ficha, admin, "Ficha no encontrada")
        historial = list(ficha.historial_tratamientos or [])
        historial.append(entry.model_dump())
        ficha.historial_tratamientos = historial
        await session.flush()
        await session.refresh(ficha)
        await redis_cache.invalidate_fichas(admin.tenant_id)
        return ficha
