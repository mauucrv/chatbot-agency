"""
Admin CRUD endpoints for sales (ventas, detalles_venta).
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

import pytz

from app.config import settings
from app.database import get_session_context
from app.models.models import (
    AdminUser,
    Cita,
    DetalleVenta,
    FichaCliente,
    MetodoPago,
    MovimientoInventario,
    Producto,
    TipoMovimiento,
    TipoVenta,
    Venta,
)
from app.schemas.schemas import VentaCreate, VentaResponse
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import check_tenant_access, get_current_admin, require_admin_role

router = APIRouter(prefix="/ventas", tags=["Admin Ventas"])


class PaginatedVentas(BaseModel):
    items: list[VentaResponse]
    total: int
    page: int
    page_size: int


class ResumenDia(BaseModel):
    total_ventas: int
    ingresos_total: float
    por_metodo: list[dict]


@router.get("", response_model=PaginatedVentas)
async def list_ventas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    fecha_desde: Optional[datetime] = None,
    fecha_hasta: Optional[datetime] = None,
    tipo: Optional[str] = None,
    metodo_pago: Optional[str] = None,
    ficha_cliente_id: Optional[int] = None,
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        q = select(Venta).options(selectinload(Venta.detalles)).where(Venta.tenant_id == admin.tenant_id)
        count_q = select(func.count()).select_from(Venta).where(Venta.tenant_id == admin.tenant_id)

        if fecha_desde:
            q = q.where(Venta.created_at >= fecha_desde)
            count_q = count_q.where(Venta.created_at >= fecha_desde)
        if fecha_hasta:
            q = q.where(Venta.created_at <= fecha_hasta)
            count_q = count_q.where(Venta.created_at <= fecha_hasta)
        if tipo:
            q = q.where(Venta.tipo == TipoVenta(tipo))
            count_q = count_q.where(Venta.tipo == TipoVenta(tipo))
        if metodo_pago:
            q = q.where(Venta.metodo_pago == MetodoPago(metodo_pago))
            count_q = count_q.where(Venta.metodo_pago == MetodoPago(metodo_pago))
        if ficha_cliente_id:
            q = q.where(Venta.ficha_cliente_id == ficha_cliente_id)
            count_q = count_q.where(Venta.ficha_cliente_id == ficha_cliente_id)

        total = (await session.execute(count_q)).scalar()

        q = q.order_by(Venta.created_at.desc())
        q = q.offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(q)

        return PaginatedVentas(
            items=result.scalars().unique().all(),
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get("/resumen-dia", response_model=ResumenDia)
async def resumen_dia(admin: AdminUser = Depends(get_current_admin)):
    tz = pytz.timezone(settings.calendar_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    async with get_session_context() as session:
        agg = (await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(Venta.total), 0.0).label("ingresos"),
            ).where(Venta.created_at >= today_start, Venta.created_at < today_end, Venta.tenant_id == admin.tenant_id)
        )).one()

        metodos = await session.execute(
            select(Venta.metodo_pago, func.count(), func.coalesce(func.sum(Venta.total), 0.0))
            .where(Venta.created_at >= today_start, Venta.created_at < today_end, Venta.tenant_id == admin.tenant_id)
            .group_by(Venta.metodo_pago)
        )

        return ResumenDia(
            total_ventas=agg.total,
            ingresos_total=float(agg.ingresos),
            por_metodo=[
                {"metodo": row[0].value, "cantidad": row[1], "total": float(row[2])}
                for row in metodos.all()
            ],
        )


@router.get("/{venta_id}", response_model=VentaResponse)
async def get_venta(venta_id: int, admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Venta).options(selectinload(Venta.detalles)).where(Venta.id == venta_id, Venta.tenant_id == admin.tenant_id)
        )
        venta = result.scalar_one_or_none()
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        return venta


@router.post("", response_model=VentaResponse, status_code=status.HTTP_201_CREATED)
async def create_venta(
    body: VentaCreate, admin: AdminUser = Depends(require_admin_role)
):
    async with get_session_context() as session:
        # Validate FK references
        if body.ficha_cliente_id:
            ficha = await session.get(FichaCliente, body.ficha_cliente_id)
            check_tenant_access(ficha, admin, "Ficha de cliente no encontrada")

        if body.cita_id:
            cita = await session.get(Cita, body.cita_id)
            check_tenant_access(cita, admin, "Cita no encontrada")

        # Build line items and calculate totals
        has_productos = False
        has_servicios = False
        detalles = []
        subtotal = 0.0

        for det in body.detalles:
            det_subtotal = det.cantidad * det.precio_unitario
            subtotal += det_subtotal

            detalle = DetalleVenta(
                producto_id=det.producto_id,
                descripcion=det.descripcion,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                subtotal=det_subtotal,
            )

            if det.producto_id:
                has_productos = True
                producto = await session.get(Producto, det.producto_id)
                check_tenant_access(producto, admin, f"Producto '{det.descripcion}' no encontrado o inactivo")
                if not producto.activo:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Producto '{det.descripcion}' no encontrado o inactivo",
                    )
                if producto.cantidad < det.cantidad:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente para '{producto.nombre}'. Disponible: {producto.cantidad}",
                    )
            else:
                has_servicios = True

            detalles.append(detalle)

        # Determine sale type
        if has_productos and has_servicios:
            tipo = TipoVenta.MIXTA
        elif has_productos:
            tipo = TipoVenta.PRODUCTO
        else:
            tipo = TipoVenta.SERVICIO

        if body.descuento > subtotal:
            raise HTTPException(
                status_code=400,
                detail="El descuento no puede ser mayor al subtotal",
            )

        total = subtotal - body.descuento

        venta = Venta(
            ficha_cliente_id=body.ficha_cliente_id,
            cita_id=body.cita_id,
            tipo=tipo,
            subtotal=subtotal,
            descuento=body.descuento,
            total=total,
            metodo_pago=MetodoPago(body.metodo_pago),
            notas=body.notas,
            vendedor=body.vendedor,
            detalles=detalles,
            tenant_id=admin.tenant_id,
        )
        session.add(venta)
        await session.flush()

        # Create inventory movements for product items
        for det in body.detalles:
            if det.producto_id:
                producto = await session.get(Producto, det.producto_id)
                cantidad_anterior = producto.cantidad
                cantidad_nueva = cantidad_anterior - det.cantidad
                mov = MovimientoInventario(
                    producto_id=det.producto_id,
                    tipo=TipoMovimiento.SALIDA,
                    cantidad=det.cantidad,
                    cantidad_anterior=cantidad_anterior,
                    cantidad_nueva=cantidad_nueva,
                    motivo="Venta",
                    referencia=f"venta:{venta.id}",
                )
                session.add(mov)
                producto.cantidad = cantidad_nueva

        await session.flush()
        await session.refresh(venta)

        # Reload with detalles
        result = await session.execute(
            select(Venta).options(selectinload(Venta.detalles)).where(Venta.id == venta.id)
        )
        venta = result.scalar_one()

        await redis_cache.invalidate_ventas(admin.tenant_id)
        await redis_cache.invalidate_inventario(admin.tenant_id)
        await redis_cache.invalidate_informes(admin.tenant_id)
        return venta


@router.delete("/{venta_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venta(venta_id: int, admin: AdminUser = Depends(require_admin_role)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Venta).options(selectinload(Venta.detalles)).where(Venta.id == venta_id, Venta.tenant_id == admin.tenant_id)
        )
        venta = result.scalar_one_or_none()
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        # Reverse inventory movements for product items
        for detalle in venta.detalles:
            if detalle.producto_id:
                producto = await session.get(Producto, detalle.producto_id)
                if producto:
                    cantidad_anterior = producto.cantidad
                    cantidad_nueva = cantidad_anterior + detalle.cantidad
                    mov = MovimientoInventario(
                        producto_id=detalle.producto_id,
                        tipo=TipoMovimiento.ENTRADA,
                        cantidad=detalle.cantidad,
                        cantidad_anterior=cantidad_anterior,
                        cantidad_nueva=cantidad_nueva,
                        motivo="Reverso por eliminacion de venta",
                        referencia=f"reverso_venta:{venta_id}",
                    )
                    session.add(mov)
                    producto.cantidad = cantidad_nueva

        await session.delete(venta)
        await redis_cache.invalidate_ventas(admin.tenant_id)
        await redis_cache.invalidate_inventario(admin.tenant_id)
        await redis_cache.invalidate_informes(admin.tenant_id)
