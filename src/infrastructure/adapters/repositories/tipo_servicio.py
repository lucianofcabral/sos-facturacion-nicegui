from __future__ import annotations

from src.domain.exceptions import EntityNotFoundError
from src.domain.models.entities import TipoServicio
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

    async def remove(self, id: int) -> None:
        await self._delete(id=id)
