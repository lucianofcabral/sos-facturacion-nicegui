"""Use cases for CapitaPeriodo (CRUD)."""

from __future__ import annotations

from src.domain.dto import CreateCapitaPeriodo, EditCapitaPeriodo
from src.domain.models.entities import CapitaPeriodo
from src.domain.ports.uow import UnitOfWorkPort


async def crear_capita_periodo(
    uow: UnitOfWorkPort, dto: CreateCapitaPeriodo
) -> CapitaPeriodo:
    entity = CapitaPeriodo(
        periodo_id=dto.periodo_id,
        tipo_servicio_id=dto.tipo_servicio_id,
        capitas=dto.capitas,
    )
    creado = await uow.capitas_periodo.add(entity)
    await uow.commit()
    return creado


async def listar_capitas_periodo(uow: UnitOfWorkPort) -> list[CapitaPeriodo]:
    return await uow.capitas_periodo.list()


async def editar_capita_periodo(
    uow: UnitOfWorkPort,
    periodo_id: int,
    tipo_servicio_id: int,
    dto: EditCapitaPeriodo,
) -> CapitaPeriodo:
    existente = await uow.capitas_periodo.get(periodo_id, tipo_servicio_id)
    actualizado = CapitaPeriodo(
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_servicio_id,
        capitas=dto.capitas if dto.capitas is not None else existente.capitas,
    )
    resultado = await uow.capitas_periodo.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_capita_periodo(
    uow: UnitOfWorkPort, periodo_id: int, tipo_servicio_id: int
) -> None:
    await uow.capitas_periodo.remove(periodo_id, tipo_servicio_id)
    await uow.commit()
