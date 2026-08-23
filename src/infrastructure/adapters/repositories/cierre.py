from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.exceptions import EntityNotFoundError, PeriodoNotClosedError
from src.domain.models.entities import Cierre
from src.domain.ports.repositories import CierreRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class CierreRepositoryPg(PostgresRepository, CierreRepository):
    table = "cierre"
    entity_type = Cierre
    key_fields = ("id",)
    auto_fields = ("id", "creado_en")

    async def get(self, id: int) -> Cierre:
        ent = await self._fetch_one(id=id)
        if ent is None:
            raise EntityNotFoundError(self.entity_type.__name__, id)
        return ent

    async def remove(self, id: int) -> None:
        await self._delete(id=id)

    async def next_version(self, periodo_id: int) -> int:
        sql = (
            f"SELECT COALESCE(MAX(version), 0) + 1 AS next_version "
            f"FROM {self.table} WHERE periodo_id = %s"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (periodo_id,))
            row = await cur.fetchone()
        assert row is not None
        return int(row["next_version"])

    async def get_oficial(self, periodo_id: int) -> Cierre | None:
        sql = (
            f"SELECT * FROM {self.table} "
            f"WHERE periodo_id = %s AND estado = 'oficial'"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (periodo_id,))
            row = await cur.fetchone()
        return self._row_to_entity(row) if row is not None else None

    async def demote_oficial(self, periodo_id: int) -> None:
        """Demote the period's official cierre to ``no_oficial``.

        Must run before inserting the replacement official cierre because
        ``uq_cierre_oficial`` is non-deferrable and checked per statement.
        """
        sql = (
            f"UPDATE {self.table} SET estado = 'no_oficial' "
            f"WHERE periodo_id = %s AND estado = 'oficial'"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (periodo_id,))
            if cur.rowcount == 0:
                raise PeriodoNotClosedError(periodo_id)
