"""Shared async repository base (SIN ORM).

Implements the uniform contract from ``Repository[T]`` (add/list/update) against
a raw psycopg async connection, keyed by natural or composite keys (no surrogate
ids). Concrete repositories supply ``table``, ``entity_type``, ``key_fields``
(the primary-key columns) and ``auto_fields`` (columns the DB generates, e.g. a
serial ``id``; empty for natural keys). Domain-specific queries are added per repo.

Table names are constant literals from our own code (never user input), so
f-string interpolation here is safe.
"""

from __future__ import annotations

from typing import Any, TypeVar

from psycopg.rows import dict_row
from pydantic import BaseModel

from src.domain.exceptions import EntityNotFoundError

E = TypeVar("E", bound=BaseModel)

# Object-valued fields on the entities that are NOT stored as flat columns.
_NESTED_FIELDS = {"periodo", "tipo_servicio"}


class PostgresRepository:
    # Subclasses must set these.
    table: str
    entity_type: type[E]
    key_fields: tuple[str, ...]
    auto_fields: tuple[str, ...] = ()

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def _scalar_fields(self) -> list[str]:
        return [
            name for name in self.entity_type.model_fields if name not in _NESTED_FIELDS
        ]

    def _row_to_entity(self, row: dict) -> E:
        fields = self.entity_type.model_fields
        data = {key: value for key, value in row.items() if key in fields}
        return self.entity_type(**data)

    async def _fetch_one(self, **key: object) -> E | None:
        where = " AND ".join(f"{k} = %s" for k in key)
        sql = f"SELECT * FROM {self.table} WHERE {where}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, list(key.values()))
            row = await cur.fetchone()
        return self._row_to_entity(row) if row is not None else None

    async def _delete(self, **key: object) -> None:
        where = " AND ".join(f"{k} = %s" for k in key)
        sql = f"DELETE FROM {self.table} WHERE {where}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, list(key.values()))
            if cur.rowcount == 0:
                raise EntityNotFoundError(
                    self.entity_type.__name__, tuple(key.values())
                )

    async def add(self, entity: E) -> E:
        fields = [f for f in self._scalar_fields() if f not in self.auto_fields]
        cols = ", ".join(fields)
        placeholders = ", ".join(["%s"] * len(fields))
        values = [getattr(entity, f) for f in fields]
        sql = f"INSERT INTO {self.table} ({cols}) VALUES ({placeholders}) RETURNING *"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, values)
            row = await cur.fetchone()
        assert row is not None
        return self._row_to_entity(row)

    async def list(self) -> list[E]:
        sql = f"SELECT * FROM {self.table}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def update(self, entity: E) -> E:
        set_fields = [f for f in self._scalar_fields() if f not in self.key_fields]
        where_fields = list(self.key_fields)
        set_clause = ", ".join(f"{f} = %s" for f in set_fields)
        where_clause = " AND ".join(f"{f} = %s" for f in where_fields)
        values = [getattr(entity, f) for f in set_fields] + [
            getattr(entity, f) for f in where_fields
        ]
        sql = f"UPDATE {self.table} SET {set_clause} WHERE {where_clause} RETURNING *"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, values)
            row = await cur.fetchone()
        if row is None:
            key_values = [getattr(entity, f) for f in where_fields]
            raise EntityNotFoundError(self.entity_type.__name__, tuple(key_values))
        return self._row_to_entity(row)
