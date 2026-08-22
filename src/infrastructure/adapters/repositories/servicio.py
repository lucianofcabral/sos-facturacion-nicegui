from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.models.entities import Servicio
from src.domain.ports.repositories import ServicioRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class ServicioRepositoryPg(PostgresRepository, ServicioRepository):
    table = "servicio"
    entity_type = Servicio
    key_fields = ("nro_servicio",)
    auto_fields = ()

    async def get(self, nro_servicio: str) -> Servicio | None:
        return await self._fetch_one(nro_servicio=nro_servicio)

    async def remove(self, nro_servicio: str) -> None:
        await self._delete(nro_servicio=nro_servicio)

    async def get_by_nro_servicio(self, nro_servicio: str) -> Servicio | None:
        return await self._fetch_one(nro_servicio=nro_servicio)

    async def get_by_fields(
        self,
        codigo_radio: str | None = None,
        fecha: object = None,
        dominio: str | None = None,
        cod_productor: int | None = None,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
    ) -> list[Servicio]:
        filters = {
            "codigo_radio": codigo_radio,
            "fecha": fecha,
            "dominio": dominio,
            "cod_productor": cod_productor,
            "periodo_id": periodo_id,
            "tipo_servicio_id": tipo_servicio_id,
        }
        conditions: list[str] = []
        params: list[object] = []
        for column, value in filters.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM {self.table} {where}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]
