"""PostgreSQL adapter for UsuarioApp (SIN ORM).

The ``creado_en`` / ``actualizado_en`` columns are database-managed
(DEFAULT now()), so they are excluded from INSERT/UPDATE via ``auto_fields``
and an overridden ``update``.
"""

from __future__ import annotations

from uuid import UUID

from psycopg.rows import dict_row

from src.domain.exceptions import EntityNotFoundError
from src.domain.models.user import UsuarioApp
from src.domain.ports.repositories import UsuarioAppRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class UsuarioAppRepositoryPg(PostgresRepository, UsuarioAppRepository):
    table = "usuario"
    entity_type = UsuarioApp
    key_fields = ("id",)
    # creado_en / actualizado_en are managed by the database (DEFAULT now()).
    auto_fields = ("creado_en", "actualizado_en")

    async def get(self, id: UUID) -> UsuarioApp:
        ent = await self._fetch_one(id=id)
        if ent is None:
            raise EntityNotFoundError(self.entity_type.__name__, id)
        return ent

    async def get_by_nombre(self, nombre: str) -> UsuarioApp | None:
        return await self._fetch_one(nombre=nombre)

    async def get_by_email(self, email: str) -> UsuarioApp | None:
        return await self._fetch_one(email=email)

    async def remove(self, id: UUID) -> None:
        await self._delete(id=id)

    async def update(self, entity: UsuarioApp) -> UsuarioApp:
        # Do not overwrite database-managed columns.
        set_fields = [
            f
            for f in self._scalar_fields()
            if f not in self.key_fields and f not in self.auto_fields
        ]
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
