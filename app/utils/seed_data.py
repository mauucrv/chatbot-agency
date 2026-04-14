"""
Seed initial data into the database.
"""

import structlog
from datetime import time

from sqlalchemy import select

from app.config import settings
from app.database import get_session_context
from app.models import (
    Estilista,
    HorarioEstilista,
    InformacionGeneral,
    KeywordHumano,
    ServicioBelleza,
    DiaSemana,
)

logger = structlog.get_logger(__name__)


async def _sync_salon_info_from_env() -> None:
    """
    Sync basic salon info from environment variables to the database.

    Runs on every startup so that changes to SALON_NAME, SALON_ADDRESS,
    SALON_PHONE, or SALON_HOURS in the hosting environment take effect
    immediately. Only updates fields whose env var is explicitly set.
    """
    async with get_session_context() as session:
        result = await session.execute(select(InformacionGeneral).limit(1))
        info = result.scalar_one_or_none()
        if not info:
            return

        updates = {}
        if settings.salon_name and info.nombre_salon != settings.salon_name:
            updates["nombre_salon"] = settings.salon_name
            info.nombre_salon = settings.salon_name
        if settings.salon_address and info.direccion != settings.salon_address:
            updates["direccion"] = settings.salon_address
            info.direccion = settings.salon_address
        if settings.salon_phone and info.telefono != settings.salon_phone:
            updates["telefono"] = settings.salon_phone
            info.telefono = settings.salon_phone
        if settings.salon_hours and info.horario != settings.salon_hours:
            updates["horario"] = settings.salon_hours
            info.horario = settings.salon_hours

        if updates:
            await session.commit()
            # Invalidate Redis cache so fresh values propagate
            from app.services.redis_cache import redis_cache
            # Use tenant_id from the info record if available, otherwise default tenant
            tenant_id = getattr(info, "tenant_id", 1) or 1
            await redis_cache.invalidate_info(tenant_id)
            logger.info("Salon info synced from environment variables", updated_fields=list(updates.keys()))


async def seed_initial_data() -> None:
    """
    Seed initial data into the database.

    This function creates default data if the database is empty:
    - Sample services
    - Sample stylists with schedules
    - Salon information
    - Human handoff keywords
    """
    logger.info("Checking for initial data...")

    async with get_session_context() as session:
        # Check if data already exists
        result = await session.execute(select(ServicioBelleza).limit(1))
        if result.scalar_one_or_none():
            logger.info("Data already exists, skipping seed")
            # Always sync salon info from env vars
            await _sync_salon_info_from_env()
            return

        # Skip seed data if disabled (new client deployments)
        if not settings.seed_data_enabled:
            logger.info("Seed data disabled via SEED_DATA_ENABLED=false, skipping")
            await _sync_salon_info_from_env()
            return

        logger.info("Seeding initial data...")

        # Create services
        services = [
            ServicioBelleza(
                servicio="Consulta gratuita",
                descripcion="Videollamada para conocer tus necesidades y explorar cómo AgencyBot puede ayudarte",
                precio=0,
                duracion_minutos=30,
                estilistas_disponibles=["Mauricio Demo"],
            ),
            ServicioBelleza(
                servicio="Prueba gratuita del chatbot",
                descripcion="Configuración inicial del chatbot para tu negocio + 1 semana de prueba sin costo ni compromiso",
                precio=0,
                duracion_minutos=45,
                estilistas_disponibles=["Mauricio Demo"],
            ),
        ]

        for service in services:
            session.add(service)

        # Create consultants
        stylists_data = [
            {
                "nombre": "Mauricio Demo",
                "telefono": "",
                "email": "contacto@example.com",
                "especialidades": ["Chatbots", "Automatizaciones", "Consultoría IA"],
                "horarios": [
                    (DiaSemana.LUNES, time(9, 0), time(18, 0)),
                    (DiaSemana.MARTES, time(9, 0), time(18, 0)),
                    (DiaSemana.MIERCOLES, time(9, 0), time(18, 0)),
                    (DiaSemana.JUEVES, time(9, 0), time(18, 0)),
                    (DiaSemana.VIERNES, time(9, 0), time(18, 0)),
                ],
            },
        ]

        for stylist_data in stylists_data:
            stylist = Estilista(
                nombre=stylist_data["nombre"],
                telefono=stylist_data["telefono"],
                email=stylist_data["email"],
                especialidades=stylist_data["especialidades"],
            )
            session.add(stylist)
            await session.flush()

            for dia, hora_inicio, hora_fin in stylist_data["horarios"]:
                horario = HorarioEstilista(
                    estilista_id=stylist.id,
                    dia=dia,
                    hora_inicio=hora_inicio,
                    hora_fin=hora_fin,
                )
                session.add(horario)

        # Create business information
        salon_info = InformacionGeneral(
            nombre_salon=settings.salon_name,
            direccion=settings.salon_address or "",
            telefono=settings.salon_phone or "",
            horario=settings.salon_hours or "Lunes a Viernes: 9:00 AM - 6:00 PM",
            descripcion="AgencyBot es una agencia especializada en automatizaciones, chatbots e inteligencia artificial para negocios.",
            politicas="• Las consultas y pruebas son 100% gratuitas y sin compromiso\n• Cancelaciones con mínimo 2 horas de anticipación",
            redes_sociales={
                "instagram": "@agencybot_demo",
                "facebook": "AgencyBot",
            },
        )
        session.add(salon_info)

        # Create human handoff keywords
        keywords = [
            "hablar con humano",
            "hablar con persona",
            "agente humano",
            "quiero hablar con alguien",
            "operador",
            "persona real",
            "atencion al cliente",
            "atención al cliente",
            "queja",
            "reclamación",
            "reclamacion",
            "problema urgente",
            "emergencia",
        ]

        for keyword in keywords:
            session.add(KeywordHumano(keyword=keyword))

        await session.commit()
        logger.info("Initial data seeded successfully")
