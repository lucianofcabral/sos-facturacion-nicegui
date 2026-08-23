"""Repository ports (interfaces) for the domain layer.

Ports operate on domain *entities*, not DTOs. Entities use natural or composite
keys (no surrogate ids), so each port declares its own get/remove signature.
"""

from __future__ import annotations

from datetime import date
from typing import Protocol, TypeVar
from uuid import UUID

from src.domain.exceptions import (
    EntityNotFoundError,  # noqa: F401  (raised by get/remove)
)
from src.domain.models.entities import (
    Alicuota,
    CapitaPeriodo,
    Cierre,
    Periodo,
    Servicio,
    TipoServicio,
)
from src.domain.models.user import UsuarioApp

T = TypeVar("T")


class Repository(Protocol[T]):
    """Generic add/list/update contract shared by all repositories.

    get/remove are not part of this base because their key shape varies per
    entity (integer id, natural string key, or composite key).
    """

    def add(self, entity: T) -> T:
        """Persist a new entity and return it."""
        ...

    def list(self) -> list[T]:
        """Return all entities."""
        ...

    def update(self, entity: T) -> T:
        """Persist changes keyed by the entity's natural key."""
        ...


class PeriodoRepository(Repository[Periodo], Protocol):
    def get(self, id: int) -> Periodo:
        """Return the periodo by id or raise EntityNotFoundError."""
        ...

    def remove(self, id: int) -> None:
        """Delete the periodo by id or raise EntityNotFoundError."""
        ...

    def get_by_anio(self, anio: int) -> list[Periodo]: ...

    def get_by_anio_mes(self, anio: int, mes: int) -> list[Periodo]: ...

    def get_previous(self, anio: int, mes: int) -> Periodo | None: ...

    def get_following(self, anio: int, mes: int) -> list[Periodo]: ...


class TipoServicioRepository(Repository[TipoServicio], Protocol):
    def get(self, id: int) -> TipoServicio: ...
    def remove(self, id: int) -> None: ...


class AlicuotaRepository(Repository[Alicuota], Protocol):
    def get(self, periodo_id: int, tipo_servicio_id: int) -> Alicuota | None: ...
    def remove(self, periodo_id: int, tipo_servicio_id: int) -> None: ...
    def get_by_keys(
        self,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
        coeficiente: float | None = None,
    ) -> list[Alicuota]: ...

    def reemplazar_por_periodo(
        self, periodo_id: int, alicuotas: list[Alicuota]
    ) -> None: ...


class ServicioRepository(Repository[Servicio], Protocol):
    def get(self, nro_servicio: str) -> Servicio | None: ...
    def remove(self, nro_servicio: str) -> None: ...
    def get_by_nro_servicio(self, nro_servicio: str) -> Servicio | None: ...
    def get_by_fields(
        self,
        codigo_radio: str | None = None,
        fecha: date | None = None,
        dominio: str | None = None,
        cod_productor: int | None = None,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
    ) -> list[Servicio]: ...


class CapitaPeriodoRepository(Repository[CapitaPeriodo], Protocol):
    def get(self, periodo_id: int, tipo_servicio_id: int) -> CapitaPeriodo | None: ...
    def remove(self, periodo_id: int, tipo_servicio_id: int) -> None: ...
    def get_by_fields(
        self,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
    ) -> list[CapitaPeriodo]: ...


class CierreRepository(Repository[Cierre], Protocol):
    def get(self, id: int) -> Cierre: ...
    def remove(self, id: int) -> None: ...
    def next_version(self, periodo_id: int) -> int: ...
    def get_oficial(self, periodo_id: int) -> Cierre | None: ...
    def demote_oficial(self, periodo_id: int) -> None: ...


class UsuarioAppRepository(Repository[UsuarioApp], Protocol):
    def get(self, id: UUID) -> UsuarioApp:
        """Return the usuario by id or raise EntityNotFoundError."""
        ...

    def remove(self, id: UUID) -> None:
        """Delete the usuario by id or raise EntityNotFoundError."""
        ...

    def get_by_nombre(self, nombre: str) -> UsuarioApp | None: ...

    def get_by_email(self, email: str) -> UsuarioApp | None: ...
