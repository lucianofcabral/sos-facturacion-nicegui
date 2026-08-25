from __future__ import annotations

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.domain.exceptions import EntityNotFoundError
from src.domain.models.entities import Periodo
from src.domain.ports.repositories import PeriodoRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class PeriodoRepositoryPg(PostgresRepository, PeriodoRepository):
    table = "periodo"
    entity_type = Periodo
    key_fields = ("id",)
    auto_fields = ("id",)

    async def add(self, entity: Periodo) -> Periodo:
        fields = [f for f in self._scalar_fields() if f not in self.auto_fields]
        cols = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        values: list[object] = [
            self._wrap_hojas(f, getattr(entity, f)) for f in fields
        ]
        sql = f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders}) RETURNING *"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, values)
            row = await cur.fetchone()
        assert row is not None
        return self._row_to_entity(row)

    async def update(self, entity: Periodo) -> Periodo:
        set_fields = [f for f in self._scalar_fields() if f not in self.key_fields]
        where_fields = list(self.key_fields)
        set_clause = ", ".join(f"{f} = %s" for f in set_fields)
        where_clause = " AND ".join(f"{f} = %s" for f in where_fields)
        values: list[object] = [
            self._wrap_hojas(f, getattr(entity, f)) for f in set_fields
        ]
        values += [getattr(entity, f) for f in where_fields]
        sql = f"UPDATE {self.table} SET {set_clause} WHERE {where_clause} RETURNING *"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, values)
            row = await cur.fetchone()
        if row is None:
            key_values = [getattr(entity, f) for f in where_fields]
            raise EntityNotFoundError(self.entity_type.__name__, tuple(key_values))
        return self._row_to_entity(row)

    @staticmethod
    def _wrap_hojas(field: str, value: object) -> object:
        """Adapt ``hojas_entrada`` to jsonb; other fields pass through unchanged."""
        if field == "hojas_entrada" and value is not None:
            return Jsonb(value)
        return value

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

    async def get_following(self, anio: int, mes: int) -> list[Periodo]:
        sql = (
            f"SELECT * FROM {self.table} WHERE (anio, mes) > (%s, %s) "
            f"ORDER BY anio ASC, mes ASC"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (anio, mes))
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]
