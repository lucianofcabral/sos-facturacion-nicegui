from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.exceptions import EntityNotFoundError
from src.domain.models.entities import Periodo
from src.domain.ports.repositories import PeriodoRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class PeriodoRepositoryPg(PostgresRepository, PeriodoRepository):
    table = "periodo"
    entity_type = Periodo
    key_fields = ("id",)
    auto_fields = ("id",)

    async def get(self, id: int) -> Periodo:
        ent = await self._fetch_one(id=id)
        if ent is None:
            raise EntityNotFoundError(self.entity_type.__name__, id)
        return ent

    async def remove(self, id: int) -> None:
        await self._delete(id=id)

    async def get_by_anio(self, anio: int) -> list[Periodo]:
        sql = f"SELECT * FROM {self.table} WHERE anio = %s"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (anio,))
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def get_by_anio_mes(self, anio: int, mes: int) -> list[Periodo]:
        sql = f"SELECT * FROM {self.table} WHERE anio = %s AND mes = %s"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (anio, mes))
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def get_previous(self, anio: int, mes: int) -> Periodo | None:
        sql = (
            f"SELECT * FROM {self.table} WHERE (anio, mes) < (%s, %s) "
            f"ORDER BY anio DESC, mes DESC LIMIT 1"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (anio, mes))
            row = await cur.fetchone()
        return self._row_to_entity(row) if row is not None else None
