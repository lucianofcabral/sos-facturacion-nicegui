from __future__ import annotations

from psycopg.rows import dict_row

from src.domain.models.entities import Alicuota
from src.domain.ports.repositories import AlicuotaRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class AlicuotaRepositoryPg(PostgresRepository, AlicuotaRepository):
    table = "alicuota"
    entity_type = Alicuota
    key_fields = ("periodo_id", "tipo_servicio_id", "coeficiente")
    auto_fields = ()

    @staticmethod
    def _coef_key(coeficiente: float) -> str:
        """Normalize a float coeficiente to a 6-decimal string.

        The column is NUMERIC(10,6); formatting to 6 decimals makes the equality
        match the stored value exactly (avoids float binary-representation drift).
        """
        return f"{float(coeficiente):.6f}"

    async def get(self, periodo_id: int, tipo_servicio_id: int, coeficiente: float) -> Alicuota | None:
        return await self._fetch_one(
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
            coeficiente=self._coef_key(coeficiente),
        )

    async def remove(self, periodo_id: int, tipo_servicio_id: int, coeficiente: float) -> None:
        await self._delete(
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
            coeficiente=self._coef_key(coeficiente),
        )

    async def get_by_keys(
        self,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
        coeficiente: float | None = None,
    ) -> list[Alicuota]:
        conditions: list[str] = []
        params: list[object] = []
        if periodo_id is not None:
            conditions.append("periodo_id = %s")
            params.append(periodo_id)
        if tipo_servicio_id is not None:
            conditions.append("tipo_servicio_id = %s")
            params.append(tipo_servicio_id)
        if coeficiente is not None:
            conditions.append("coeficiente >= %s")
            params.append(coeficiente)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = "ORDER BY coeficiente ASC LIMIT 1" if coeficiente is not None else ""
        sql = f"SELECT * FROM {self.table} {where} {order}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def reemplazar_por_periodo(
        self, periodo_id: int, alicuotas: list[Alicuota]
    ) -> None:
        """Atomically replace the period's alicuotas on the same connection.

        Uses a raw DELETE (not ``_delete``) so replacing with an empty set is
        legal, followed by a single ``executemany`` INSERT.
        """
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"DELETE FROM {self.table} WHERE periodo_id = %s", (periodo_id,)
            )
            if alicuotas:
                rows = [
                    (a.periodo_id, a.tipo_servicio_id, a.coeficiente, a.valor)
                    for a in alicuotas
                ]
                await cur.executemany(
                    f"INSERT INTO {self.table} "
                    "(periodo_id, tipo_servicio_id, coeficiente, valor) "
                    "VALUES (%s, %s, %s, %s)",
                    rows,
                )

    async def get_effective(self, anio: int, mes: int) -> list[Alicuota]:
        """Return the latest alícuotas at a period ``(anio, mes)`` or earlier.

        Alícuotas are sparse: they only exist on periods whose cierre carried a
        cambio (aumento distinto de cero). This returns the set of the most
        recent such period at or before the given one, so a period without its
        own alícuotas inherits the previous effective set.
        """
        sql = (
            f"SELECT a.* FROM {self.table} a "
            f"WHERE a.periodo_id = ("
            f"  SELECT a2.periodo_id FROM {self.table} a2 "
            f"  JOIN periodo p2 ON p2.id = a2.periodo_id "
            f"  WHERE (p2.anio, p2.mes) <= (%s, %s) "
            f"  ORDER BY p2.anio DESC, p2.mes DESC LIMIT 1"
            f") ORDER BY a.coeficiente ASC"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (anio, mes))
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]
