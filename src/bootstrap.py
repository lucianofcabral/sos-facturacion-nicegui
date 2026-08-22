"""Bootstrap de la aplicación: crea el admin inicial al arrancar.

Idempotente: si el admin ya existe, no lo modifica. Se registra vía
``ui.on_startup`` para correr en el loop de la aplicación (mismo loop que el
pool de conexiones), evitando problemas de cross-loop en psycopg.

La contraseña está hardcodeada solo para facilitar las pruebas iniciales;
en producción debe moverse a una variable de entorno (.env).
"""

from __future__ import annotations

import os

from src.application.use_cases.usuario import asegurar_admin_inicial
from src.infrastructure.adapters.uow import PostgresUoW

ADMIN_NOMBRE = os.getenv("ADMIN_NOMBRE", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")


async def bootstrap() -> None:
    """Asegura el usuario admin inicial. No bloquea el arranque de la app.

    Cualquier fallo (p. ej. la base no está disponible) se registra y se
    continúa: la app arranca igual y el login fallará hasta que se resuelva.
    """
    if not ADMIN_PASSWORD:
        print("[bootstrap] ADMIN_PASSWORD no está configurada en .env; no se crea el admin inicial.")
        return
    try:
        async with PostgresUoW() as uow:
            creado = await asegurar_admin_inicial(uow, ADMIN_NOMBRE, ADMIN_PASSWORD)
    except Exception as exc:  # no debe romper el arranque de la app
        print(f"[bootstrap] No se pudo asegurar el admin inicial: {exc}")
        return
    if creado is None:
        print(f"[bootstrap] Usuario admin '{ADMIN_NOMBRE}' ya existe; no se modifica.")
    else:
        print(f"[bootstrap] Usuario admin '{ADMIN_NOMBRE}' creado.")
