"""Use cases for Servicio (CRUD)."""

from __future__ import annotations

from src.domain.dto import CreateServicio, EditServicio
from src.domain.models.entities import Servicio
from src.domain.ports.uow import UnitOfWorkPort


async def crear_servicio(uow: UnitOfWorkPort, dto: CreateServicio) -> Servicio:
    entity = Servicio(
        nro_servicio=dto.nro_servicio,
        codigo_radio=dto.codigo_radio,
        fecha=dto.fecha,
        dominio=dto.dominio,
        cod_productor=dto.cod_productor,
        periodo_id=dto.periodo_id,
        tipo_servicio_id=dto.tipo_servicio_id,
    )
    creado = await uow.servicios.add(entity)
    await uow.commit()
    return creado


async def listar_servicios(uow: UnitOfWorkPort) -> list[Servicio]:
    return await uow.servicios.list()


async def editar_servicio(
    uow: UnitOfWorkPort, nro_servicio: str, dto: EditServicio
) -> Servicio:
    existente = await uow.servicios.get(nro_servicio)
    actualizado = Servicio(
        nro_servicio=existente.nro_servicio,
        codigo_radio=dto.codigo_radio
        if dto.codigo_radio is not None
        else existente.codigo_radio,
        fecha=dto.fecha if dto.fecha is not None else existente.fecha,
        dominio=dto.dominio if dto.dominio is not None else existente.dominio,
        cod_productor=dto.cod_productor
        if dto.cod_productor is not None
        else existente.cod_productor,
        periodo_id=dto.periodo_id
        if dto.periodo_id is not None
        else existente.periodo_id,
        tipo_servicio_id=dto.tipo_servicio_id
        if dto.tipo_servicio_id is not None
        else existente.tipo_servicio_id,
    )
    resultado = await uow.servicios.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_servicio(uow: UnitOfWorkPort, nro_servicio: str) -> None:
    await uow.servicios.remove(nro_servicio)
    await uow.commit()
