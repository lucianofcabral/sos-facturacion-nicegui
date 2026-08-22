"""Use cases for Periodo (CRUD)."""

from __future__ import annotations

from src.domain.dto import CreatePeriodo, EditPeriodo
from src.domain.models.entities import Periodo
from src.domain.ports.uow import UnitOfWorkPort


async def crear_periodo(uow: UnitOfWorkPort, dto: CreatePeriodo) -> Periodo:
    entity = Periodo(nombre=dto.nombre, anio=dto.anio, mes=dto.mes)
    creado = await uow.periodos.add(entity)
    await uow.commit()
    return creado


async def listar_periodos(uow: UnitOfWorkPort) -> list[Periodo]:
    return await uow.periodos.list()


async def editar_periodo(
    uow: UnitOfWorkPort, id: int, dto: EditPeriodo
) -> Periodo:
    existente = await uow.periodos.get(id)
    actualizado = Periodo(
        id=existente.id,
        nombre=dto.nombre if dto.nombre is not None else existente.nombre,
        anio=dto.anio if dto.anio is not None else existente.anio,
        mes=dto.mes if dto.mes is not None else existente.mes,
    )
    resultado = await uow.periodos.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_periodo(uow: UnitOfWorkPort, id: int) -> None:
    await uow.periodos.remove(id)
    await uow.commit()
