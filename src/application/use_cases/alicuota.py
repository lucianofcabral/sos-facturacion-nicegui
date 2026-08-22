"""Use cases for Alicuota (CRUD + búsqueda por coeficiente superior más cercano)."""

from __future__ import annotations

from src.domain.dto import CreateAlicuota, EditAlicuota
from src.domain.models.entities import Alicuota
from src.domain.ports.uow import UnitOfWorkPort


async def crear_alicuota(uow: UnitOfWorkPort, dto: CreateAlicuota) -> Alicuota:
    entity = Alicuota(
        periodo_id=dto.periodo_id,
        tipo_servicio_id=dto.tipo_servicio_id,
        coeficiente=dto.coeficiente,
        valor=dto.valor,
    )
    creado = await uow.alicuotas.add(entity)
    await uow.commit()
    return creado


async def listar_alicuotas(uow: UnitOfWorkPort) -> list[Alicuota]:
    return await uow.alicuotas.list()


async def editar_alicuota(
    uow: UnitOfWorkPort,
    periodo_id: int,
    tipo_servicio_id: int,
    dto: EditAlicuota,
) -> Alicuota:
    await uow.alicuotas.get(periodo_id, tipo_servicio_id)  # lanza si no existe
    actualizado = Alicuota(
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_servicio_id,
        coeficiente=dto.coeficiente,
        valor=dto.valor,
    )
    resultado = await uow.alicuotas.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_alicuota(
    uow: UnitOfWorkPort, periodo_id: int, tipo_servicio_id: int
) -> None:
    await uow.alicuotas.remove(periodo_id, tipo_servicio_id)
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
