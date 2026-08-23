"""Use cases for Alicuota (CRUD + búsqueda por coeficiente superior más cercano).

La identidad de una alícuota es ``(periodo_id, tipo_servicio_id, coeficiente)``.
Las mutaciones validan la progresión del valor: para un tipo dado, ordenadas por
coeficiente, los valores deben ser monótonos no decrecientes.
"""

from __future__ import annotations

from itertools import pairwise

from src.application.authorization import requerir_admin
from src.domain.dto import CreateAlicuota, EditAlicuota
from src.domain.enums import RolUsuario
from src.domain.exceptions import AlicuotaProgresionError
from src.domain.models.entities import Alicuota
from src.domain.ports.uow import UnitOfWorkPort


def validar_progresion(alicuotas: list[Alicuota]) -> None:
    """Raise ``AlicuotaProgresionError`` if values break monotonic non-decreasing
    order by coeficiente.

    For each consecutive pair (by coeficiente), the superior value must be >= the
    inferior one.
    """
    ordenadas = sorted(alicuotas, key=lambda a: a.coeficiente)
    for inferior, superior in pairwise(ordenadas):
        if superior.valor < inferior.valor:
            raise AlicuotaProgresionError(
                superior.tipo_servicio_id,
                inferior=(inferior.coeficiente, inferior.valor),
                superior=(superior.coeficiente, superior.valor),
            )


async def crear_alicuota(
    uow: UnitOfWorkPort, dto: CreateAlicuota, *, rol: RolUsuario
) -> Alicuota:
    requerir_admin(rol)
    entity = Alicuota(
        periodo_id=dto.periodo_id,
        tipo_servicio_id=dto.tipo_servicio_id,
        coeficiente=dto.coeficiente,
        valor=dto.valor,
    )
    actuales = await uow.alicuotas.get_by_keys(
        periodo_id=dto.periodo_id, tipo_servicio_id=dto.tipo_servicio_id
    )
    validar_progresion([*actuales, entity])
    creado = await uow.alicuotas.add(entity)
    await uow.commit()
    return creado


async def listar_alicuotas(uow: UnitOfWorkPort) -> list[Alicuota]:
    return await uow.alicuotas.list()


async def editar_alicuota(
    uow: UnitOfWorkPort,
    periodo_id: int,
    tipo_servicio_id: int,
    coeficiente_old: float,
    dto: EditAlicuota,
    *,
    rol: RolUsuario,
) -> Alicuota:
    """Replace the alicuota at ``coeficiente_old`` with the edited one.

    Validates the resulting set (existing minus old, plus new) for progression
    before removing the old row and inserting the new one. Supports changing both
    ``valor`` and ``coeficiente``.
    """
    requerir_admin(rol)
    nueva = Alicuota(
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_servicio_id,
        coeficiente=dto.coeficiente,
        valor=dto.valor,
    )
    actuales = await uow.alicuotas.get_by_keys(
        periodo_id=periodo_id, tipo_servicio_id=tipo_servicio_id
    )
    otras = [a for a in actuales if a.coeficiente != coeficiente_old]
    validar_progresion([*otras, nueva])
    await uow.alicuotas.remove(periodo_id, tipo_servicio_id, coeficiente_old)
    await uow.alicuotas.add(nueva)
    await uow.commit()
    return nueva


async def eliminar_alicuota(
    uow: UnitOfWorkPort,
    periodo_id: int,
    tipo_servicio_id: int,
    coeficiente: float,
    *,
    rol: RolUsuario,
) -> None:
    requerir_admin(rol)
    await uow.alicuotas.remove(periodo_id, tipo_servicio_id, coeficiente)
    await uow.commit()


async def buscar_alicuota_por_coeficiente(
    uow: UnitOfWorkPort, periodo_id: int, tipo_servicio_id: int, coeficiente: float
) -> Alicuota | None:
    """Devuelve la alícuota con el menor coeficiente >= al buscado (bracket)."""
    candidatos = await uow.alicuotas.get_by_keys(
        periodo_id=periodo_id, tipo_servicio_id=tipo_servicio_id
    )
    superiores = [a for a in candidatos if a.coeficiente >= coeficiente]
    if not superiores:
        return None
    return min(superiores, key=lambda a: a.coeficiente)
