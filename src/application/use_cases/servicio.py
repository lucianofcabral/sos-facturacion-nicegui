"""Use cases for Servicio (CRUD + Excel import)."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Literal

from src.application.services.excel_servicios import ImportadorServiciosExcel
from src.domain.dto import CreateServicio, EditServicio
from src.domain.exceptions import ImportServiciosError
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


async def importar_servicios(
    uow: UnitOfWorkPort,
    periodo_id: int,
    archivo: Path | BytesIO,
    modo: Literal["upsert", "reemplazo"],
) -> dict:
    """Import services from an Excel workbook into ``periodo_id``.

    Parses the workbook (single-month validation + sheets 1-3), resolves every
    ``codigo_radio`` to a ``tipo_servicio.codigo`` (failing before any write on
    an unknown code), then persists in ONE explicit commit. ``upsert`` matches
    by ``nro_servicio`` (update existing, insert new, never delete); ``reemplazo``
    replaces the whole period-scoped set. Never creates or touches a cierre.
    """
    filas = ImportadorServiciosExcel().leer(archivo)

    codigos = {fila.codigo_radio for fila in filas}
    tipos: dict[str, int] = {}
    for codigo in codigos:
        tipo = await uow.tipos_servicio.get_by_codigo(str(int(codigo)))
        if tipo is None or tipo.id is None:
            raise ImportServiciosError(
                f"Tipo de servicio desconocido para código {codigo!r}"
            )
        tipos[str(int(codigo))] = tipo.id

    nuevos = [
        Servicio(
            nro_servicio=fila.nro_servicio,
            codigo_radio=fila.codigo_radio,
            fecha=fila.fecha,
            dominio=fila.dominio,
            cod_productor=fila.cod_productor,
            periodo_id=periodo_id,
            tipo_servicio_id=tipos[str(int(fila.codigo_radio))],
        )
        for fila in filas
    ]

    if modo == "upsert":
        creados = 0
        actualizados = 0
        for nuevo in nuevos:
            existente = await uow.servicios.get(nuevo.nro_servicio)
            if existente is None:
                await uow.servicios.add(nuevo)
                creados += 1
            else:
                await uow.servicios.update(nuevo)
                actualizados += 1
        eliminados = 0
    elif modo == "reemplazo":
        previos = await uow.servicios.get_by_fields(periodo_id=periodo_id)
        await uow.servicios.reemplazar_por_periodo(periodo_id, nuevos)
        creados = len(nuevos)
        actualizados = 0
        eliminados = len(previos)
    else:
        raise ImportServiciosError(f"Modo inválido: {modo!r}")

    await uow.commit()
    return {"creados": creados, "actualizados": actualizados, "eliminados": eliminados}
