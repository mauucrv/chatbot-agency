"""
Admin report endpoints — aggregated data from sales, inventory, clients, and stylists.
"""

import csv
import io
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, text

import pytz

from app.config import settings
from app.database import get_session_context
from app.models.models import (
    AdminUser,
    Cita,
    DetalleVenta,
    EstadoCita,
    Estilista,
    FichaCliente,
    MovimientoInventario,
    Producto,
    Venta,
)
from app.services.redis_cache import redis_cache
from app.utils.admin_deps import get_current_admin

router = APIRouter(prefix="/informes", tags=["Admin Informes"])

INFORMES_CACHE_TTL = 180


# ── Response models ─────────────────────────────────────────


class InformeVentas(BaseModel):
    total_ingresos: float
    total_ventas: int
    ticket_promedio: float
    ventas_por_dia: list[dict]
    ventas_por_metodo_pago: list[dict]
    productos_mas_vendidos: list[dict]
    servicios_mas_vendidos: list[dict]


class InformeInventario(BaseModel):
    valor_total_stock: float
    total_productos: int
    productos_bajo_stock: list[dict]
    productos_por_vencer: list[dict]
    movimientos_recientes: list[dict]


class InformeClientes(BaseModel):
    total_clientes: int
    clientes_nuevos_periodo: int
    clientes_recurrentes: int
    top_clientes: list[dict]
    frecuencia_visitas: list[dict]


class InformeEstilistas(BaseModel):
    rendimiento: list[dict]


# ── Sales report ────────────────────────────────────────────


@router.get("/ventas", response_model=InformeVentas)
async def informe_ventas(
    fecha_desde: datetime = Query(...),
    fecha_hasta: datetime = Query(...),
    admin: AdminUser = Depends(get_current_admin),
):
    cache_key = f"informes:ventas:{fecha_desde.date()}:{fecha_hasta.date()}"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return InformeVentas(**cached)

    async with get_session_context() as session:
        base_filter = [Venta.tenant_id == admin.tenant_id, Venta.created_at >= fecha_desde, Venta.created_at <= fecha_hasta]

        # Totals
        agg = (await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(Venta.total), 0.0).label("ingresos"),
            ).where(*base_filter)
        )).one()

        total_ventas = agg.total
        total_ingresos = float(agg.ingresos)
        ticket_promedio = round(total_ingresos / total_ventas, 2) if total_ventas else 0.0

        # By day
        dia_result = await session.execute(
            select(
                func.date_trunc("day", Venta.created_at).label("fecha"),
                func.count().label("cantidad"),
                func.sum(Venta.total).label("total"),
            )
            .where(*base_filter)
            .group_by("fecha")
            .order_by("fecha")
        )
        ventas_por_dia = [
            {"fecha": row.fecha.isoformat(), "cantidad": row.cantidad, "total": float(row.total)}
            for row in dia_result.all()
        ]

        # By payment method
        metodo_result = await session.execute(
            select(Venta.metodo_pago, func.count(), func.sum(Venta.total))
            .where(*base_filter)
            .group_by(Venta.metodo_pago)
        )
        ventas_por_metodo_pago = [
            {"metodo": row[0].value, "cantidad": row[1], "total": float(row[2])}
            for row in metodo_result.all()
        ]

        # Top products sold
        prod_result = await session.execute(
            select(
                DetalleVenta.descripcion,
                func.sum(DetalleVenta.cantidad).label("cantidad"),
                func.sum(DetalleVenta.subtotal).label("total"),
            )
            .join(Venta, DetalleVenta.venta_id == Venta.id)
            .where(*base_filter, DetalleVenta.producto_id.isnot(None))
            .group_by(DetalleVenta.descripcion)
            .order_by(func.sum(DetalleVenta.cantidad).desc())
            .limit(10)
        )
        productos_mas_vendidos = [
            {"nombre": row.descripcion, "cantidad": int(row.cantidad), "total": float(row.total)}
            for row in prod_result.all()
        ]

        # Top services sold
        svc_result = await session.execute(
            select(
                DetalleVenta.descripcion,
                func.sum(DetalleVenta.cantidad).label("cantidad"),
                func.sum(DetalleVenta.subtotal).label("total"),
            )
            .join(Venta, DetalleVenta.venta_id == Venta.id)
            .where(*base_filter, DetalleVenta.producto_id.is_(None))
            .group_by(DetalleVenta.descripcion)
            .order_by(func.sum(DetalleVenta.cantidad).desc())
            .limit(10)
        )
        servicios_mas_vendidos = [
            {"nombre": row.descripcion, "cantidad": int(row.cantidad), "total": float(row.total)}
            for row in svc_result.all()
        ]

    result = InformeVentas(
        total_ingresos=total_ingresos,
        total_ventas=total_ventas,
        ticket_promedio=ticket_promedio,
        ventas_por_dia=ventas_por_dia,
        ventas_por_metodo_pago=ventas_por_metodo_pago,
        productos_mas_vendidos=productos_mas_vendidos,
        servicios_mas_vendidos=servicios_mas_vendidos,
    )

    await redis_cache.set_admin_cache(admin.tenant_id, cache_key, result.model_dump(), INFORMES_CACHE_TTL)
    return result


@router.get("/ventas/exportar")
async def exportar_ventas(
    fecha_desde: datetime = Query(...),
    fecha_hasta: datetime = Query(...),
    admin: AdminUser = Depends(get_current_admin),
):
    async with get_session_context() as session:
        result = await session.execute(
            select(Venta)
            .where(Venta.tenant_id == admin.tenant_id, Venta.created_at >= fecha_desde, Venta.created_at <= fecha_hasta)
            .order_by(Venta.created_at.desc())
            .limit(10000)
        )
        ventas = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Fecha", "Tipo", "Subtotal", "Descuento", "Total", "Metodo Pago", "Vendedor"])
    for v in ventas:
        writer.writerow([
            v.id,
            v.created_at.isoformat(),
            v.tipo.value,
            v.subtotal,
            v.descuento,
            v.total,
            v.metodo_pago.value,
            v.vendedor or "",
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ventas.csv"},
    )


# ── Inventory report ────────────────────────────────────────


@router.get("/inventario", response_model=InformeInventario)
async def informe_inventario(admin: AdminUser = Depends(get_current_admin)):
    cache_key = "informes:inventario"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return InformeInventario(**cached)

    tz = pytz.timezone(settings.calendar_timezone)
    now = datetime.now(tz)

    async with get_session_context() as session:
        # Total stock value
        valor_result = (await session.execute(
            select(
                func.count().label("total"),
                func.coalesce(func.sum(Producto.cantidad * Producto.costo_unitario), 0.0).label("valor"),
            )
            .where(Producto.tenant_id == admin.tenant_id, Producto.activo.is_(True))
        )).one()

        # Low stock
        bajo_result = await session.execute(
            select(Producto)
            .where(Producto.tenant_id == admin.tenant_id, Producto.activo.is_(True), Producto.cantidad <= Producto.stock_minimo)
            .order_by(Producto.cantidad)
            .limit(20)
        )
        productos_bajo_stock = [
            {"id": p.id, "nombre": p.nombre, "cantidad": p.cantidad, "stock_minimo": p.stock_minimo}
            for p in bajo_result.scalars().all()
        ]

        # Expiring soon (30 days)
        limite = now + timedelta(days=30)
        vencer_result = await session.execute(
            select(Producto)
            .where(
                Producto.tenant_id == admin.tenant_id,
                Producto.activo.is_(True),
                Producto.fecha_vencimiento.isnot(None),
                Producto.fecha_vencimiento <= limite,
            )
            .order_by(Producto.fecha_vencimiento)
            .limit(20)
        )
        productos_por_vencer = [
            {
                "id": p.id,
                "nombre": p.nombre,
                "fecha_vencimiento": p.fecha_vencimiento.isoformat(),
                "cantidad": p.cantidad,
            }
            for p in vencer_result.scalars().all()
        ]

        # Recent movements
        mov_result = await session.execute(
            select(MovimientoInventario, Producto.nombre)
            .join(Producto, MovimientoInventario.producto_id == Producto.id)
            .where(Producto.tenant_id == admin.tenant_id)
            .order_by(MovimientoInventario.created_at.desc())
            .limit(20)
        )
        movimientos_recientes = [
            {
                "fecha": row[0].created_at.isoformat(),
                "producto": row[1],
                "tipo": row[0].tipo.value,
                "cantidad": row[0].cantidad,
                "motivo": row[0].motivo,
            }
            for row in mov_result.all()
        ]

    result = InformeInventario(
        valor_total_stock=float(valor_result.valor),
        total_productos=valor_result.total,
        productos_bajo_stock=productos_bajo_stock,
        productos_por_vencer=productos_por_vencer,
        movimientos_recientes=movimientos_recientes,
    )

    await redis_cache.set_admin_cache(admin.tenant_id, cache_key, result.model_dump(), INFORMES_CACHE_TTL)
    return result


@router.get("/inventario/exportar")
async def exportar_inventario(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(Producto).where(Producto.tenant_id == admin.tenant_id, Producto.activo.is_(True)).order_by(Producto.nombre).limit(10000)
        )
        productos = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nombre", "Marca", "Categoria", "Cantidad", "Unidad", "Costo Unitario", "Precio Venta", "Stock Minimo", "Fecha Vencimiento"])
    for p in productos:
        writer.writerow([
            p.id, p.nombre, p.marca or "", p.categoria.value, p.cantidad, p.unidad or "",
            p.costo_unitario, p.precio_venta or "", p.stock_minimo,
            p.fecha_vencimiento.isoformat() if p.fecha_vencimiento else "",
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventario.csv"},
    )


# ── Clients report ──────────────────────────────────────────


@router.get("/clientes", response_model=InformeClientes)
async def informe_clientes(
    fecha_desde: datetime = Query(...),
    fecha_hasta: datetime = Query(...),
    admin: AdminUser = Depends(get_current_admin),
):
    cache_key = f"informes:clientes:{fecha_desde.date()}:{fecha_hasta.date()}"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return InformeClientes(**cached)

    async with get_session_context() as session:
        total_clientes = (await session.execute(
            select(func.count()).select_from(FichaCliente).where(FichaCliente.tenant_id == admin.tenant_id, FichaCliente.activo.is_(True))
        )).scalar()

        clientes_nuevos = (await session.execute(
            select(func.count()).select_from(FichaCliente).where(
                FichaCliente.tenant_id == admin.tenant_id,
                FichaCliente.created_at >= fecha_desde,
                FichaCliente.created_at <= fecha_hasta,
            )
        )).scalar()

        # Top clients by spending (from ventas linked to fichas)
        top_result = await session.execute(
            select(
                FichaCliente.nombre,
                FichaCliente.telefono,
                func.count(Venta.id).label("total_ventas"),
                func.coalesce(func.sum(Venta.total), 0.0).label("total_gastado"),
            )
            .join(Venta, Venta.ficha_cliente_id == FichaCliente.id)
            .where(FichaCliente.tenant_id == admin.tenant_id, Venta.created_at >= fecha_desde, Venta.created_at <= fecha_hasta)
            .group_by(FichaCliente.id, FichaCliente.nombre, FichaCliente.telefono)
            .order_by(func.sum(Venta.total).desc())
            .limit(10)
        )
        top_clientes = [
            {
                "nombre": row.nombre,
                "telefono": row.telefono,
                "total_ventas": row.total_ventas,
                "total_gastado": float(row.total_gastado),
            }
            for row in top_result.all()
        ]

        # Visit frequency — count appointments per client phone
        freq_result = await session.execute(
            text("""
                SELECT
                    CASE
                        WHEN cnt = 1 THEN '1 vez'
                        WHEN cnt BETWEEN 2 AND 3 THEN '2-3 veces'
                        WHEN cnt BETWEEN 4 AND 6 THEN '4-6 veces'
                        ELSE '7+ veces'
                    END AS rango,
                    COUNT(*) AS cantidad
                FROM (
                    SELECT telefono_cliente, COUNT(*) AS cnt
                    FROM citas
                    WHERE inicio >= :desde AND inicio <= :hasta
                      AND tenant_id = :tenant_id
                    GROUP BY telefono_cliente
                ) sub
                GROUP BY rango
                ORDER BY MIN(cnt)
            """),
            {"desde": fecha_desde, "hasta": fecha_hasta, "tenant_id": admin.tenant_id},
        )
        frecuencia_visitas = [
            {"rango": row.rango, "cantidad": row.cantidad}
            for row in freq_result.all()
        ]

        # Recurring clients (2+ visits in period)
        recurrentes = (await session.execute(
            text("""
                SELECT COUNT(*) FROM (
                    SELECT telefono_cliente
                    FROM citas
                    WHERE inicio >= :desde AND inicio <= :hasta
                      AND tenant_id = :tenant_id
                    GROUP BY telefono_cliente
                    HAVING COUNT(*) >= 2
                ) sub
            """),
            {"desde": fecha_desde, "hasta": fecha_hasta, "tenant_id": admin.tenant_id},
        )).scalar()

    result = InformeClientes(
        total_clientes=total_clientes,
        clientes_nuevos_periodo=clientes_nuevos,
        clientes_recurrentes=recurrentes or 0,
        top_clientes=top_clientes,
        frecuencia_visitas=frecuencia_visitas,
    )

    await redis_cache.set_admin_cache(admin.tenant_id, cache_key, result.model_dump(), INFORMES_CACHE_TTL)
    return result


@router.get("/clientes/exportar")
async def exportar_clientes(admin: AdminUser = Depends(get_current_admin)):
    async with get_session_context() as session:
        result = await session.execute(
            select(FichaCliente).where(FichaCliente.tenant_id == admin.tenant_id, FichaCliente.activo.is_(True)).order_by(FichaCliente.nombre)
        )
        fichas = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Nombre", "Telefono", "Email", "Tipo Cabello", "Tipo Piel", "Alergias", "Preferencias"])
    for f in fichas:
        writer.writerow([
            f.id, f.nombre, f.telefono, f.email or "",
            f.tipo_cabello.value if f.tipo_cabello else "",
            f.tipo_piel.value if f.tipo_piel else "",
            f.alergias or "", f.preferencias or "",
        ])
    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"},
    )


# ── Stylist performance report ──────────────────────────────


@router.get("/estilistas", response_model=InformeEstilistas)
async def informe_estilistas(
    fecha_desde: datetime = Query(...),
    fecha_hasta: datetime = Query(...),
    admin: AdminUser = Depends(get_current_admin),
):
    cache_key = f"informes:estilistas:{fecha_desde.date()}:{fecha_hasta.date()}"
    cached = await redis_cache.get_admin_cache(admin.tenant_id, cache_key)
    if cached:
        return InformeEstilistas(**cached)

    async with get_session_context() as session:
        result = await session.execute(
            select(
                Estilista.nombre,
                func.count(Cita.id).label("citas_totales"),
                func.count(Cita.id).filter(Cita.estado == EstadoCita.COMPLETADA).label("completadas"),
                func.count(Cita.id).filter(Cita.estado == EstadoCita.CANCELADA).label("canceladas"),
                func.coalesce(
                    func.sum(Cita.precio_total).filter(Cita.estado == EstadoCita.COMPLETADA), 0.0
                ).label("ingresos"),
            )
            .join(Cita, Cita.estilista_id == Estilista.id)
            .where(
                Estilista.tenant_id == admin.tenant_id,
                Estilista.activo.is_(True),
                Cita.inicio >= fecha_desde,
                Cita.inicio <= fecha_hasta,
            )
            .group_by(Estilista.id, Estilista.nombre)
            .order_by(func.sum(Cita.precio_total).filter(Cita.estado == EstadoCita.COMPLETADA).desc())
        )

        rendimiento = []
        for row in result.all():
            tasa_cancelacion = round(row.canceladas / row.citas_totales * 100, 1) if row.citas_totales else 0.0
            rendimiento.append({
                "nombre": row.nombre,
                "citas_totales": row.citas_totales,
                "completadas": row.completadas,
                "canceladas": row.canceladas,
                "ingresos": float(row.ingresos),
                "tasa_cancelacion": tasa_cancelacion,
            })

    result_model = InformeEstilistas(rendimiento=rendimiento)
    await redis_cache.set_admin_cache(admin.tenant_id, cache_key, result_model.model_dump(), INFORMES_CACHE_TTL)
    return result_model
