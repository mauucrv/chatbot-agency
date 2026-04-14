"""
Admin endpoints for salon information and handoff keywords.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.database import get_session_context
from app.models.models import AdminUser, InformacionGeneral, KeywordHumano
from app.schemas.schemas import SalonInfoBase, SalonInfoResponse
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/info", tags=["Admin Info"])


# ── Salon Info ──────────────────────────────────────────────


@router.get("", response_model=SalonInfoResponse | None)
async def get_info(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(InformacionGeneral)
            .where(InformacionGeneral.tenant_id == admin.tenant_id)
            .limit(1)
        )
        return result.scalar_one_or_none()


@router.put("", response_model=SalonInfoResponse)
async def update_info(body: SalonInfoBase, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        result = await session.execute(
            select(InformacionGeneral)
            .where(InformacionGeneral.tenant_id == admin.tenant_id)
            .limit(1)
        )
        info = result.scalar_one_or_none()
        if info:
            for field, value in body.model_dump().items():
                setattr(info, field, value)
        else:
            info = InformacionGeneral(**body.model_dump(), tenant_id=admin.tenant_id)
            session.add(info)
        await session.flush()
        await session.refresh(info)
        await redis_cache.invalidate_info(admin.tenant_id)
        return info


# ── Keywords ────────────────────────────────────────────────


class KeywordResponse(BaseModel):
    id: int
    keyword: str
    activo: bool

    class Config:
        from_attributes = True


class KeywordCreate(BaseModel):
    keyword: str = Field(..., min_length=1, max_length=100)


@router.get("/keywords", response_model=list[KeywordResponse])
async def list_keywords(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(KeywordHumano)
            .where(KeywordHumano.tenant_id == admin.tenant_id)
            .order_by(KeywordHumano.keyword)
        )
        return result.scalars().all()


@router.post("/keywords", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(body: KeywordCreate, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        existing = await session.execute(
            select(KeywordHumano).where(
                KeywordHumano.keyword == body.keyword.lower(),
                KeywordHumano.tenant_id == admin.tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Keyword ya existe")
        kw = KeywordHumano(keyword=body.keyword.lower(), tenant_id=admin.tenant_id)
        session.add(kw)
        await session.flush()
        await session.refresh(kw)
        await redis_cache.invalidate_keywords(admin.tenant_id)
        return kw


@router.put("/keywords/{keyword_id}", response_model=KeywordResponse)
async def toggle_keyword(
    keyword_id: int,
    activo: bool,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        kw = await session.get(KeywordHumano, keyword_id)
        check_tenant_access(kw, admin, "Keyword no encontrada")
        kw.activo = activo
        await session.flush()
        await session.refresh(kw)
        await redis_cache.invalidate_keywords(admin.tenant_id)
        return kw


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(keyword_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        kw = await session.get(KeywordHumano, keyword_id)
        check_tenant_access(kw, admin, "Keyword no encontrada")
        await session.delete(kw)
        await redis_cache.invalidate_keywords(admin.tenant_id)
