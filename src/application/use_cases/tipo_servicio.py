"""Use cases for TipoServicio (CRUD)."""

from __future__ import annotations

from src.domain.dto import CreateTipoServicio, EditTipoServicio
from src.domain.models.entities import MetricasTipoServicio, TipoServicio
from src.domain.ports.uow import UnitOfWorkPort


async def crear_tipo_servicio(
    uow: UnitOfWorkPort, dto: CreateTipoServicio
) -> TipoServicio:
    entity = TipoServicio(
        rama=dto.rama, nombre=dto.nombre, codigo=dto.codigo, categoria=dto.categoria
    )
    creado = await uow.tipos_servicio.add(entity)
    await uow.commit()
    return creado


async def listar_tipos_servicio(uow: UnitOfWorkPort) -> list[TipoServicio]:
    return await uow.tipos_servicio.list()


async def metricas_tipo_servicio(
    uow: UnitOfWorkPort, tipo_servicio_id: int
) -> MetricasTipoServicio:
    return await uow.tipos_servicio.get_metricas(tipo_servicio_id)


async def editar_tipo_servicio(
    uow: UnitOfWorkPort, id: int, dto: EditTipoServicio
) -> TipoServicio:
    existente = await uow.tipos_servicio.get(id)
    actualizado = TipoServicio(
        id=existente.id,
        rama=dto.rama if dto.rama is not None else existente.rama,
        nombre=dto.nombre if dto.nombre is not None else existente.nombre,
        codigo=dto.codigo if dto.codigo is not None else existente.codigo,
        categoria=dto.categoria if dto.categoria is not None else existente.categoria,
    )
    resultado = await uow.tipos_servicio.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_tipo_servicio(uow: UnitOfWorkPort, id: int) -> None:
    await uow.tipos_servicio.remove(id)
    await uow.commit()
