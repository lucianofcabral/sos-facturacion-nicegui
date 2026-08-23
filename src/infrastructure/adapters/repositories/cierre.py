from __future__ import annotations

import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.domain.exceptions import EntityNotFoundError, PeriodoNotClosedError
from src.domain.models.entities import Cierre
from src.domain.ports.repositories import CierreRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


def _snapshot_dumps(obj: object) -> str:
    """JSON-serialize a snapshot with JSON-native coercion.

    psycopg3 does not auto-adapt ``dict`` -> jsonb, and the default ``Jsonb``
    serializer (``json.dumps``) raises on ``Decimal`` and ``date``. This default
    handler converts ``Decimal`` -> fixed 2dp str and ``date``/``datetime`` ->
    ISO before dumping.
    """

    def _default(o: object) -> str:
        if isinstance(o, Decimal):
            return str(o.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, date):
            return o.isoformat()
        raise TypeError(
            f"Object of type {type(o).__name__} is not JSON serializable"
        )

    return json.dumps(obj, default=_default)


class CierreRepositoryPg(PostgresRepository, CierreRepository):
    table = "cierre"
    entity_type = Cierre
    key_fields = ("id",)
    auto_fields = ("id", "creado_en")

    async def add(self, entity: Cierre) -> Cierre:
        fields = [f for f in self._scalar_fields() if f not in self.auto_fields]
        cols = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        values: list[object] = []
        for f in fields:
            value = getattr(entity, f)
            if f == "snapshot" and value is not None:
                value = Jsonb(value, dumps=_snapshot_dumps)
            values.append(value)
        sql = f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders}) RETURNING *"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, values)
            row = await cur.fetchone()
        assert row is not None
        return self._row_to_entity(row)

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

    async def get_oficiales_recientes(
        self, periodo_id: int, limit: int = 12
    ) -> list[Cierre]:
        sql = (
            f"SELECT c.* FROM {self.table} c "
            f"JOIN periodo p ON p.id = c.periodo_id "
            f"WHERE c.estado = 'oficial' "
            f"AND (p.anio, p.mes) < (SELECT anio, mes FROM periodo WHERE id = %s) "
            f"ORDER BY p.anio DESC, p.mes DESC LIMIT %s"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (periodo_id, limit))
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

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
