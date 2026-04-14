"""
Admin CRUD endpoints for appointments (citas).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.agent.tools import escape_ilike
from app.database import get_session_context
from app.models.models import AdminUser, Cita, EstadoCita
from app.schemas.schemas import AppointmentResponse, AppointmentUpdate
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/citas", tags=["Admin Citas"])


class PaginatedAppointments(BaseModel):
    items: list[AppointmentResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedAppointments)
async def list_appointments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    estado: Optional[str] = None,
    estilista_id: Optional[int] = None,
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    busqueda: Optional[str] = None,
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        q = select(Cita).options(selectinload(Cita.estilista)).where(Cita.tenant_id == admin.tenant_id)
        count_q = select(func.count()).select_from(Cita).where(Cita.tenant_id == admin.tenant_id)

        # Filters
        if estado:
            q = q.where(Cita.estado == EstadoCita(estado))
            count_q = count_q.where(Cita.estado == EstadoCita(estado))
        if estilista_id:
            q = q.where(Cita.estilista_id == estilista_id)
            count_q = count_q.where(Cita.estilista_id == estilista_id)
        if fecha_desde:
            q = q.where(Cita.inicio >= fecha_desde)
            count_q = count_q.where(Cita.inicio >= fecha_desde)
        if fecha_hasta:
            q = q.where(Cita.inicio <= fecha_hasta)
            count_q = count_q.where(Cita.inicio <= fecha_hasta)
        if busqueda:
            # Uses GIN trigram index (ix_citas_nombre_cliente_trgm, ix_citas_telefono_cliente_trgm)
            pattern = f"%{escape_ilike(busqueda)}%"
            q = q.where(
                Cita.nombre_cliente.ilike(pattern)
                | Cita.telefono_cliente.ilike(pattern)
            )
            count_q = count_q.where(
                Cita.nombre_cliente.ilike(pattern)
                | Cita.telefono_cliente.ilike(pattern)
            )

        total_result = await session.execute(count_q)
        total = total_result.scalar()

        q = q.order_by(Cita.inicio.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)
        items = result.scalars().all()

        return PaginatedAppointments(
            items=items, total=total, page=page, page_size=page_size
        )


@router.get("/{cita_id}", response_model=AppointmentResponse)
async def get_appointment(cita_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Cita)
            .options(selectinload(Cita.estilista))
            .where(Cita.id == cita_id)
            .where(Cita.tenant_id == admin.tenant_id)
        )
        cita = result.scalar_one_or_none()
        if not cita:
            raise HTTPException(status_code=404, detail="Cita no encontrada")
        return cita


@router.put("/{cita_id}", response_model=AppointmentResponse)
async def update_appointment(
    cita_id: int,
    body: AppointmentUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        cita = await session.get(Cita, cita_id)
        check_tenant_access(cita, admin, "Cita no encontrada")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(cita, field, value)
        await session.flush()
        await session.refresh(cita)
        return cita


@router.patch("/{cita_id}/estado", response_model=AppointmentResponse)
async def change_appointment_status(
    cita_id: int,
    estado: str = Query(...),
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        cita = await session.get(Cita, cita_id)
        check_tenant_access(cita, admin, "Cita no encontrada")
        try:
            cita.estado = EstadoCita(estado)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Estado invalido: {estado}")
        await session.flush()
        await session.refresh(cita)
        return cita


@router.delete("/{cita_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(cita_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        cita = await session.get(Cita, cita_id)
        check_tenant_access(cita, admin, "Cita no encontrada")
        await session.delete(cita)


class AppointmentCountByStatus(BaseModel):
    estado: str
    cantidad: int


@router.get("/stats/by-status", response_model=list[AppointmentCountByStatus])
async def appointments_by_status(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Cita.estado, func.count())
            .where(Cita.tenant_id == admin.tenant_id)
            .group_by(Cita.estado)
        )
        return [
            AppointmentCountByStatus(estado=row[0].value, cantidad=row[1])
            for row in result.all()
        ]
