from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.exceptions import EntityNotFoundError
from src.domain.models.entities import MetricasTipoServicio, TipoServicio
from src.domain.ports.repositories import TipoServicioRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class TipoServicioRepositoryPg(PostgresRepository, TipoServicioRepository):
    table = "tipo_servicio"
    entity_type = TipoServicio
    key_fields = ("id",)
    auto_fields = ("id",)

    async def get(self, id: int) -> TipoServicio:
        ent = await self._fetch_one(id=id)
        if ent is None:
            raise EntityNotFoundError(self.entity_type.__name__, id)
        return ent

    async def get_by_codigo(self, codigo: str) -> TipoServicio | None:
        return await self._fetch_one(codigo=codigo)

    async def get_metricas(self, tipo_servicio_id: int) -> MetricasTipoServicio:
        sql = (
            "WITH ciclos AS ("
            "  SELECT periodo_id FROM servicio WHERE tipo_servicio_id = %s "
            "  UNION SELECT periodo_id FROM alicuota WHERE tipo_servicio_id = %s "
            "  UNION SELECT periodo_id FROM capita_periodo WHERE tipo_servicio_id = %s"
            ") SELECT "
            "  (SELECT COUNT(*) FROM servicio WHERE tipo_servicio_id = %s) AS servicios_asociados,"
            "  (SELECT COUNT(*) FROM ciclos) AS ciclos,"
            "  (SELECT p.nombre FROM periodo p JOIN ciclos c ON c.periodo_id = p.id "
            "    ORDER BY p.anio, p.mes LIMIT 1) AS primer_ciclo,"
            "  (SELECT p.nombre FROM periodo p JOIN ciclos c ON c.periodo_id = p.id "
            "    ORDER BY p.anio DESC, p.mes DESC LIMIT 1) AS ultimo_ciclo"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                sql, (tipo_servicio_id, tipo_servicio_id, tipo_servicio_id, tipo_servicio_id)
            )
            row = await cur.fetchone()
        assert row is not None
        return MetricasTipoServicio(
            servicios_asociados=row["servicios_asociados"],
            ciclos=row["ciclos"],
            primer_ciclo=row["primer_ciclo"],
            ultimo_ciclo=row["ultimo_ciclo"],
        )

    async def remove(self, id: int) -> None:
        await self._delete(id=id)
