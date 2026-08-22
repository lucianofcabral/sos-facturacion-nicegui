from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.models.entities import CapitaPeriodo
from src.domain.ports.repositories import CapitaPeriodoRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class CapitaPeriodoRepositoryPg(PostgresRepository, CapitaPeriodoRepository):
    table = "capita_periodo"
    entity_type = CapitaPeriodo
    key_fields = ("periodo_id", "tipo_servicio_id")
    auto_fields = ()

    async def get(self, periodo_id: int, tipo_servicio_id: int) -> CapitaPeriodo | None:
        return await self._fetch_one(periodo_id=periodo_id, tipo_servicio_id=tipo_servicio_id)

    async def remove(self, periodo_id: int, tipo_servicio_id: int) -> None:
        await self._delete(periodo_id=periodo_id, tipo_servicio_id=tipo_servicio_id)

    async def get_by_fields(
        self,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
    ) -> list[CapitaPeriodo]:
        conditions: list[str] = []
        params: list[object] = []
        if periodo_id is not None:
            conditions.append("periodo_id = %s")
            params.append(periodo_id)
        if tipo_servicio_id is not None:
            conditions.append("tipo_servicio_id = %s")
            params.append(tipo_servicio_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM {self.table} {where}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]
