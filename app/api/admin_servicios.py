"""
Admin CRUD endpoints for services.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func

from app.database import get_session_context
from app.models.models import AdminUser, ServicioBelleza
from app.schemas.schemas import ServiceCreate, ServiceResponse, ServiceUpdate
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/servicios", tags=["Admin Servicios"])


@router.get("", response_model=list[ServiceResponse])
async def list_services(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(ServicioBelleza)
            .where(ServicioBelleza.tenant_id == admin.tenant_id)
            .order_by(ServicioBelleza.servicio)
        )
        return result.scalars().all()


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(service_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        svc = await session.get(ServicioBelleza, service_id)
        check_tenant_access(svc, admin, "Servicio no encontrado")
        return svc


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    body: ServiceCreate, admin: AdminUser = Depends(require_admin_role)
):
    async with get_session_context() as session:
        exists = await session.execute(
            select(func.count()).where(
                ServicioBelleza.servicio == body.servicio,
                ServicioBelleza.tenant_id == admin.tenant_id,
            )
        )
        if exists.scalar():
            raise HTTPException(status_code=409, detail="Ya existe un servicio con ese nombre")
        svc = ServicioBelleza(**body.model_dump(), tenant_id=admin.tenant_id)
        session.add(svc)
        await session.flush()
        await session.refresh(svc)
        await redis_cache.invalidate_services(admin.tenant_id)
        return svc


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: int,
    body: ServiceUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        svc = await session.get(ServicioBelleza, service_id)
        check_tenant_access(svc, admin, "Servicio no encontrado")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(svc, field, value)
        await session.flush()
        await session.refresh(svc)
        await redis_cache.invalidate_services(admin.tenant_id)
        return svc


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        svc = await session.get(ServicioBelleza, service_id)
        check_tenant_access(svc, admin, "Servicio no encontrado")
        await session.delete(svc)
        await redis_cache.invalidate_services(admin.tenant_id)
