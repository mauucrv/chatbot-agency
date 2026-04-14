"""
Admin panel — aggregate router that includes all admin sub-routers.
"""

from fastapi import APIRouter

from app.api.admin_auth import router as auth_router
from app.api.admin_citas import router as citas_router
from app.api.admin_dashboard import router as dashboard_router
from app.api.admin_estadisticas import router as estadisticas_router
from app.api.admin_estilistas import router as estilistas_router
from app.api.admin_fichas import router as fichas_router
from app.api.admin_info import router as info_router
from app.api.admin_informes import router as informes_router
from app.api.admin_inventario import router as inventario_router
from app.api.admin_leads import router as leads_router
from app.api.admin_servicios import router as servicios_router
from app.api.admin_tenants import router as tenants_router
from app.api.admin_ventas import router as ventas_router

router = APIRouter(prefix="/api/admin")

router.include_router(auth_router)
router.include_router(dashboard_router)
router.include_router(servicios_router)
router.include_router(estilistas_router)
router.include_router(citas_router)
router.include_router(info_router)
router.include_router(estadisticas_router)
router.include_router(leads_router)
router.include_router(fichas_router)
router.include_router(inventario_router)
router.include_router(ventas_router)
router.include_router(informes_router)
router.include_router(tenants_router)
