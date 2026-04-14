"""
Client onboarding script.

Populates the database with a new client's business data from a JSON file.
Designed to run inside the Docker container or locally with DB access.

Usage:
    # Inside Docker container:
    docker exec -it <container> python scripts/setup_client.py scripts/client_data.json

    # Or via docker-compose:
    docker-compose exec app python scripts/setup_client.py scripts/client_data.json

    # With --clear flag to wipe existing data first (for re-setup):
    docker exec -it <container> python scripts/setup_client.py --clear scripts/client_data.json
"""

import asyncio
import json
import sys
from datetime import time
from pathlib import Path

# Add project root to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.database import get_session_context, init_db
from app.models import (
    DiaSemana,
    Estilista,
    HorarioEstilista,
    InformacionGeneral,
    KeywordHumano,
    ServicioBelleza,
)


VALID_DAYS = {d.value for d in DiaSemana}


def parse_time(t: str) -> time:
    """Parse 'HH:MM' string to time object."""
    parts = t.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def validate_data(data: dict) -> list[str]:
    """Validate the JSON data structure. Returns list of errors."""
    errors = []

    if "info" not in data:
        errors.append("Missing 'info' section")
    else:
        if not data["info"].get("nombre_salon"):
            errors.append("info.nombre_salon is required")

    if "servicios" not in data or not data["servicios"]:
        errors.append("At least one service is required in 'servicios'")
    else:
        for i, s in enumerate(data["servicios"]):
            if not s.get("servicio"):
                errors.append(f"servicios[{i}].servicio is required")
            if not isinstance(s.get("precio"), (int, float)) or s["precio"] < 0:
                errors.append(f"servicios[{i}].precio must be a positive number")
            if not isinstance(s.get("duracion_minutos"), int) or s["duracion_minutos"] <= 0:
                errors.append(f"servicios[{i}].duracion_minutos must be a positive integer")

    if "estilistas" not in data or not data["estilistas"]:
        errors.append("At least one stylist is required in 'estilistas'")
    else:
        for i, e in enumerate(data["estilistas"]):
            if not e.get("nombre"):
                errors.append(f"estilistas[{i}].nombre is required")
            for j, h in enumerate(e.get("horarios", [])):
                if h.get("dia") not in VALID_DAYS:
                    errors.append(
                        f"estilistas[{i}].horarios[{j}].dia must be one of: {', '.join(sorted(VALID_DAYS))}"
                    )
                for field in ("hora_inicio", "hora_fin"):
                    try:
                        parse_time(h[field])
                    except (KeyError, ValueError, IndexError):
                        errors.append(
                            f"estilistas[{i}].horarios[{j}].{field} must be 'HH:MM' format"
                        )

    return errors


async def clear_existing_data() -> None:
    """Remove all business data (services, stylists, info, keywords). Keeps conversations and stats."""
    async with get_session_context() as session:
        await session.execute(delete(HorarioEstilista))
        await session.execute(delete(KeywordHumano))
        await session.execute(delete(ServicioBelleza))
        await session.execute(delete(Estilista))
        await session.execute(delete(InformacionGeneral))
        await session.commit()
    print("  Existing business data cleared.")


async def seed_from_json(data: dict) -> None:
    """Populate the database from validated JSON data."""

    async with get_session_context() as session:
        # 1. Salon info
        info = data["info"]
        salon_info = InformacionGeneral(
            nombre_salon=info["nombre_salon"],
            direccion=info.get("direccion", ""),
            telefono=info.get("telefono", ""),
            horario=info.get("horario", ""),
            descripcion=info.get("descripcion", ""),
            politicas=info.get("politicas", ""),
            redes_sociales=info.get("redes_sociales"),
        )
        session.add(salon_info)
        print(f"  Salon info: {info['nombre_salon']}")

        # 2. Services
        for s in data["servicios"]:
            service = ServicioBelleza(
                servicio=s["servicio"],
                descripcion=s.get("descripcion", ""),
                precio=s["precio"],
                duracion_minutos=s["duracion_minutos"],
                estilistas_disponibles=s.get("estilistas_disponibles", []),
            )
            session.add(service)
        print(f"  Services: {len(data['servicios'])} added")

        # 3. Stylists + schedules
        for e in data["estilistas"]:
            stylist = Estilista(
                nombre=e["nombre"],
                telefono=e.get("telefono", ""),
                email=e.get("email", ""),
                especialidades=e.get("especialidades", []),
                google_calendar_id=e.get("google_calendar_id") or None,
            )
            session.add(stylist)
            await session.flush()  # Get the ID

            for h in e.get("horarios", []):
                horario = HorarioEstilista(
                    estilista_id=stylist.id,
                    dia=DiaSemana(h["dia"]),
                    hora_inicio=parse_time(h["hora_inicio"]),
                    hora_fin=parse_time(h["hora_fin"]),
                )
                session.add(horario)

            schedule_count = len(e.get("horarios", []))
            print(f"  Stylist: {e['nombre']} ({schedule_count} days)")

        # 4. Keywords
        keywords = data.get("keywords_humano", [])
        if keywords:
            for kw in keywords:
                session.add(KeywordHumano(keyword=kw.lower().strip()))
            print(f"  Keywords: {len(keywords)} added")

        await session.commit()


async def main() -> None:
    args = sys.argv[1:]

    clear_flag = False
    if "--clear" in args:
        clear_flag = True
        args.remove("--clear")

    if not args:
        print("Usage: python scripts/setup_client.py [--clear] <client_data.json>")
        print("")
        print("  --clear   Remove existing business data before importing")
        print("")
        print("See scripts/client_data_example.json for the expected format.")
        sys.exit(1)

    json_path = Path(args[0])
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)

    # Load and validate
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    errors = validate_data(data)
    if errors:
        print("Validation errors:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    print(f"Loading data from: {json_path}")
    print(f"Business: {data['info']['nombre_salon']}")
    print("")

    # Initialize DB connection
    await init_db()

    # Check if data already exists
    if not clear_flag:
        async with get_session_context() as session:
            result = await session.execute(select(ServicioBelleza).limit(1))
            if result.scalar_one_or_none():
                print("Warning: Database already has business data.")
                print("Use --clear flag to wipe and re-import.")
                print("")
                response = input("Continue anyway? (y/N): ").strip().lower()
                if response != "y":
                    print("Aborted.")
                    sys.exit(0)

    if clear_flag:
        print("Clearing existing data...")
        await clear_existing_data()

    print("Importing data...")
    await seed_from_json(data)
    print("")
    print("Done! Client data imported successfully.")


if __name__ == "__main__":
    asyncio.run(main())
