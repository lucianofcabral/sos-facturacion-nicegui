"""Fixtures para tests de use cases contra Postgres real (efímero).

testcontainers levanta un Postgres por sesión; el schema se aplica una vez y
cada test trunca los datos. Como no usamos pytest-asyncio, cada test corre
dentro de su propio event loop vía ``run_test`` (que abre y cierra el pool en
ese mismo loop, evitando reusar un pool atado a otro loop).
"""

from __future__ import annotations

import asyncio
import atexit
import os
from pathlib import Path

from testcontainers.community.postgres import PostgresContainer

pg = PostgresContainer("postgres:16-alpine", driver="psycopg")
pg.start()
os.environ["DATABASE_URL"] = pg.get_connection_url().replace("+psycopg", "")
atexit.register(pg.stop)

SCHEMA = (
    Path(__file__).parent / "src" / "infrastructure" / "db" / "schema.sql"
).read_text()

from src.infrastructure.db.connection import close_pool, get_pool  # noqa: E402

TRUNCATE = (
    "TRUNCATE TABLE usuario, periodo, tipo_servicio, alicuota, "
    "servicio, capita_periodo, cierre RESTART IDENTITY CASCADE;"
)


def _apply_schema_once() -> None:
    async def _run() -> None:
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute(SCHEMA)
            await conn.commit()
        await close_pool()

    asyncio.run(_run())


def pytest_sessionstart(session) -> None:
    _apply_schema_once()


def run_test(test_coro):
    """Ejecuta un coroutine de test con un pool fresco en su propio loop."""

    async def _wrapper():
        await close_pool()
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute(TRUNCATE)
            await conn.commit()
        result = await test_coro()
        await close_pool()
        return result

    return asyncio.run(_wrapper())
