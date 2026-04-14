"""
Admin CRUD endpoints for product inventory (productos, movimientos_inventario).
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func

import pytz

from app.agent.tools import escape_ilike
from app.config import settings
from app.database import get_session_context
from app.models.models import (
    AdminUser,
    CategoriaProducto,
    MovimientoInventario,
    Producto,
    TipoMovimiento,
)
from app.schemas.schemas import (
    MovimientoCreate,
    MovimientoResponse,
    ProductoCreate,
    ProductoResponse,
    ProductoUpdate,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/inventario", tags=["Admin Inventario"])


class PaginatedProductos(BaseModel):
    items: list[ProductoResponse]
    total: int
    page: int
    page_size: int


class PaginatedMovimientos(BaseModel):
    items: list[MovimientoResponse]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedProductos)
async def list_productos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    busqueda: Optional[str] = None,
    categoria: Optional[str] = None,
    activo: Optional[bool] = True,
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        q = select(Producto).where(Producto.tenant_id == admin.tenant_id)
        count_q = select(func.count()).select_from(Producto).where(Producto.tenant_id == admin.tenant_id)

        if activo is not None:
            q = q.where(Producto.activo == activo)
            count_q = count_q.where(Producto.activo == activo)
        if categoria:
            q = q.where(Producto.categoria == CategoriaProducto(categoria))
            count_q = count_q.where(Producto.categoria == CategoriaProducto(categoria))
        if busqueda:
            pattern = f"%{escape_ilike(busqueda)}%"
            search_filter = Producto.nombre.ilike(pattern) | Producto.marca.ilike(pattern)
            q = q.where(search_filter)
            count_q = count_q.where(search_filter)

        total = (await session.execute(count_q)).scalar()

        q = q.order_by(Producto.nombre)
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)

        return PaginatedProductos(
            items=result.scalars().all(), total=total, page=page, page_size=page_size
        )


@router.get("/bajo-stock", response_model=list[ProductoResponse])
async def bajo_stock(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Producto)
            .where(Producto.activo.is_(True), Producto.cantidad <= Producto.stock_minimo, Producto.tenant_id == admin.tenant_id)
            .order_by(Producto.cantidad)
        )
        return result.scalars().all()


@router.get("/por-vencer", response_model=list[ProductoResponse])
async def por_vencer(
    dias: int = Query(30, ge=1, le=365),
    admin: AdminUser = Depends(get_current_admin),
):
    tz = pytz.timezone(settings.calendar_timezone)
    limite = datetime.now(tz) + timedelta(days=dias)
    async with get_session_context() as session:
        result = await session.execute(
            select(Producto)
            .where(
                Producto.activo.is_(True),
                Producto.fecha_vencimiento.isnot(None),
                Producto.fecha_vencimiento <= limite,
                Producto.tenant_id == admin.tenant_id,
            )
            .order_by(Producto.fecha_vencimiento)
        )
        return result.scalars().all()


@router.get("/{producto_id}", response_model=ProductoResponse)
async def get_producto(producto_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        producto = await session.get(Producto, producto_id)
        check_tenant_access(producto, admin, "Producto no encontrado")
        return producto


@router.post("", response_model=ProductoResponse, status_code=status.HTTP_201_CREATED)
async def create_producto(
    body: ProductoCreate, admin: AdminUser = Depends(require_admin_role)
):
    async with get_session_context() as session:
        data = body.model_dump(exclude={"cantidad_inicial"})
        producto = Producto(**data, cantidad=body.cantidad_inicial, tenant_id=admin.tenant_id)
        session.add(producto)
        await session.flush()

        if body.cantidad_inicial > 0:
            mov = MovimientoInventario(
                producto_id=producto.id,
                tipo=TipoMovimiento.ENTRADA,
                cantidad=body.cantidad_inicial,
                cantidad_anterior=0,
                cantidad_nueva=body.cantidad_inicial,
                motivo="Stock inicial",
            )
            session.add(mov)
            await session.flush()

        await session.refresh(producto)
        await redis_cache.invalidate_inventario(admin.tenant_id)
        return producto


@router.put("/{producto_id}", response_model=ProductoResponse)
async def update_producto(
    producto_id: int,
    body: ProductoUpdate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        producto = await session.get(Producto, producto_id)
        check_tenant_access(producto, admin, "Producto no encontrado")
        for field, value in body.model_dump(exclude_unset=True).items():
            setattr(producto, field, value)
        await session.flush()
        await session.refresh(producto)
        await redis_cache.invalidate_inventario(admin.tenant_id)
        return producto


@router.delete("/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_producto(producto_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        producto = await session.get(Producto, producto_id)
        check_tenant_access(producto, admin, "Producto no encontrado")
        producto.activo = False
        await session.flush()
        await redis_cache.invalidate_inventario(admin.tenant_id)


@router.get("/{producto_id}/movimientos", response_model=PaginatedMovimientos)
async def list_movimientos(
    producto_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        producto = await session.get(Producto, producto_id)
        check_tenant_access(producto, admin, "Producto no encontrado")

        count_q = select(func.count()).select_from(MovimientoInventario).where(
            MovimientoInventario.producto_id == producto_id
        )
        total = (await session.execute(count_q)).scalar()

        q = (
            select(MovimientoInventario)
            .where(MovimientoInventario.producto_id == producto_id)
            .order_by(MovimientoInventario.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await session.execute(q)

        return PaginatedMovimientos(
            items=result.scalars().all(), total=total, page=page, page_size=page_size
        )


@router.post("/{producto_id}/movimientos", response_model=MovimientoResponse, status_code=status.HTTP_201_CREATED)
async def create_movimiento(
    producto_id: int,
    body: MovimientoCreate,
    admin: AdminUser = Depends(require_admin_role),
):
    async with get_session_context() as session:
        producto = await session.get(Producto, producto_id)
        check_tenant_access(producto, admin, "Producto no encontrado")

        tipo = TipoMovimiento(body.tipo)
        cantidad_anterior = producto.cantidad

        if tipo == TipoMovimiento.ENTRADA:
            cantidad_nueva = cantidad_anterior + body.cantidad
        elif tipo == TipoMovimiento.SALIDA:
            cantidad_nueva = cantidad_anterior - body.cantidad
            if cantidad_nueva < 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente. Disponible: {cantidad_anterior}",
                )
        else:  # AJUSTE
            cantidad_nueva = body.cantidad

        mov = MovimientoInventario(
            producto_id=producto_id,
            tipo=tipo,
            cantidad=body.cantidad,
            cantidad_anterior=cantidad_anterior,
            cantidad_nueva=cantidad_nueva,
            motivo=body.motivo,
        )
        session.add(mov)
        producto.cantidad = cantidad_nueva
        await session.flush()
        await session.refresh(mov)
        await redis_cache.invalidate_inventario(admin.tenant_id)
        return mov
