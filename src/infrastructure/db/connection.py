"""PostgreSQL connection pool (SIN ORM).

Reads the DSN from the environment (loaded from .env via python-dotenv) and
exposes a single async connection pool shared across the application.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL", "")
_pool: AsyncConnectionPool | None = None


def get_database_url() -> str:
    if not _DATABASE_URL:
        raise RuntimeError("DATABASE_URL no está configurada en el entorno (.env)")
    return _DATABASE_URL


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(get_database_url(), min_size=1, max_size=10, open=False)
        await _pool.open()
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
