"""Use cases for Servicio (CRUD + Excel import)."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Literal

from src.application.authorization import requerir_admin
from src.application.services.excel_servicios import ImportadorServiciosExcel
from src.domain.dto import CreateServicio, EditServicio
from src.domain.enums import RolUsuario
from src.domain.exceptions import ImportServiciosError
from src.domain.models.entities import PaginaServicios, Servicio
from src.domain.ports.uow import UnitOfWorkPort


async def crear_servicio(
    uow: UnitOfWorkPort, dto: CreateServicio, *, rol: RolUsuario
) -> Servicio:
    requerir_admin(rol)
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


async def buscar_servicios(
    uow: UnitOfWorkPort,
    periodo_id: int,
    *,
    texto: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    page: int = 1,
    page_size: int = 15,
) -> PaginaServicios:
    """Read-only: one filtered page of a period's services plus the total."""
    return await uow.servicios.search(periodo_id, texto, desde, hasta, page, page_size)


async def editar_servicio(
    uow: UnitOfWorkPort, nro_servicio: str, dto: EditServicio, *, rol: RolUsuario
) -> Servicio:
    requerir_admin(rol)
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


async def eliminar_servicio(
    uow: UnitOfWorkPort, nro_servicio: str, *, rol: RolUsuario
) -> None:
    requerir_admin(rol)
    await uow.servicios.remove(nro_servicio)
    await uow.commit()


async def importar_servicios(
    uow: UnitOfWorkPort,
    periodo_id: int,
    archivo: Path | BytesIO,
    modo: Literal["upsert", "reemplazo"],
    *,
    rol: RolUsuario,
) -> dict:
    """Import services from an Excel workbook into ``periodo_id``.

    Requires admin. Parses the workbook (single-month validation + sheets 1-3),
    resolves every ``codigo_radio`` to a ``tipo_servicio.codigo`` and persists in
    ONE explicit commit. Rows whose ``codigo_radio`` maps to no tipo are SKIPPED
    and reported in ``pendientes`` (list of ``{codigo, filas, hoja}``) so the UI can
    notify and let the user resolve them; parsing errors (mixed months, missing
    columns, empty cells) still abort before any write. ``upsert`` matches by
    ``nro_servicio`` (update existing, insert new, never delete); ``reemplazo``
    replaces the whole period-scoped set with the known rows. Never creates or
    touches a cierre.
    """
    requerir_admin(rol)
    importador = ImportadorServiciosExcel()
    filas = importador.leer(archivo)
    hojas_entrada = importador.leer_hojas(archivo)

    tipos: dict[str, int] = {}
    pendientes: list[dict] = []
    for codigo in sorted({fila.codigo_radio for fila in filas}):
        tipo = await uow.tipos_servicio.get_by_codigo(codigo)
        if tipo is None or tipo.id is None:
            filas_codigo = [f for f in filas if f.codigo_radio == codigo]
            hojas = sorted({f.hoja for f in filas_codigo if f.hoja})
            pendientes.append(
                {
                    "codigo": codigo,
                    "filas": len(filas_codigo),
                    "hoja": ", ".join(hojas),
                }
            )
        else:
            tipos[codigo] = tipo.id

    nuevos = [
        Servicio(
            nro_servicio=fila.nro_servicio,
            codigo_radio=fila.codigo_radio,
            fecha=fila.fecha,
            dominio=fila.dominio,
            cod_productor=fila.cod_productor,
            periodo_id=periodo_id,
            tipo_servicio_id=tipos[fila.codigo_radio],
        )
        for fila in filas
        if fila.codigo_radio in tipos
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

    periodo = await uow.periodos.get(periodo_id)
    await uow.periodos.update(
        periodo.model_copy(update={"hojas_entrada": hojas_entrada})
    )

    await uow.commit()
    return {
        "creados": creados,
        "actualizados": actualizados,
        "eliminados": eliminados,
        "pendientes": pendientes,
    }
