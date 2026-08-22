"""Unit of Work port.

The application layer depends on this protocol, never on a concrete adapter.
Commit is always explicit (called by the use case); rollback happens on
context exit when nothing was committed.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.ports.repositories import (
    AlicuotaRepository,
    CapitaPeriodoRepository,
    CierreRepository,
    PeriodoRepository,
    ServicioRepository,
    TipoServicioRepository,
    UsuarioAppRepository,
)


class UnitOfWorkPort(Protocol):
    periodos: PeriodoRepository
    tipos_servicio: TipoServicioRepository
    alicuotas: AlicuotaRepository
    servicios: ServicioRepository
    capitas_periodo: CapitaPeriodoRepository
    usuarios: UsuarioAppRepository
    cierres: CierreRepository

    async def commit(self) -> None:
        """Persist all changes made within this unit of work."""
        ...

    async def rollback(self) -> None:
        """Discard all changes made within this unit of work."""
        ...
