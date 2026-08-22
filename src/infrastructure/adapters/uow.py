"""Concrete PostgreSQL Unit of Work (SIN ORM, psycopg async).

Owns a connection borrowed from the shared pool for the duration of the
context manager. The use case must call ``commit()`` explicitly; if it does
not (or an exception escapes), ``__aexit__`` rolls back.
"""

from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

# PostgresUoW satisface domain.ports.uow.UnitOfWorkPort de forma estructural.
from src.infrastructure.adapters.repositories import (
    AlicuotaRepositoryPg,
    CapitaPeriodoRepositoryPg,
    CierreRepositoryPg,
    PeriodoRepositoryPg,
    ServicioRepositoryPg,
    TipoServicioRepositoryPg,
    UsuarioAppRepositoryPg,
)
from src.infrastructure.db.connection import get_pool


class PostgresUoW:
    def __init__(self, pool: AsyncConnectionPool | None = None) -> None:
        self._pool = pool
        self._conn = None
        self._committed = False

    async def __aenter__(self) -> PostgresUoW:
        if self._pool is None:
            self._pool = await get_pool()
        self._conn = await self._pool.getconn()
        self._committed = False
        self.periodos = PeriodoRepositoryPg(self._conn)
        self.tipos_servicio = TipoServicioRepositoryPg(self._conn)
        self.alicuotas = AlicuotaRepositoryPg(self._conn)
        self.servicios = ServicioRepositoryPg(self._conn)
        self.capitas_periodo = CapitaPeriodoRepositoryPg(self._conn)
        self.usuarios = UsuarioAppRepositoryPg(self._conn)
        self.cierres = CierreRepositoryPg(self._conn)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._conn is not None and (exc_type is not None or not self._committed):
                await self._conn.rollback()
        finally:
            if self._conn is not None and self._pool is not None:
                await self._pool.putconn(self._conn)
                self._conn = None

    async def commit(self) -> None:
        if self._conn is not None:
            await self._conn.commit()
            self._committed = True

    async def rollback(self) -> None:
        if self._conn is not None:
            await self._conn.rollback()
            self._committed = False
