"""Integration tests for the Excel service import (testcontainers Postgres).

Covers ``ServicioRepository.reemplazar_por_periodo`` (exact set, period scope,
empty set) and the ``importar_servicios`` use case (idempotent upsert,
period-scoped reemplazo, unknown-code fail with zero writes, no auto-cierre).
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import Workbook

from conftest import run_test
from src.application.use_cases import periodo, servicio, tipo_servicio
from src.domain.dto.create import CreatePeriodo, CreateTipoServicio
from src.domain.enums import RolUsuario
from src.domain.models.entities import Servicio
from src.infrastructure.adapters.uow import PostgresUoW

_HEADER = ["Nº Servicio", "Fecha", "Patente", "Código Radio", "Productor"]


def _xlsx(rows: list[list]) -> BytesIO:
    """Build a 5-sheet workbook with ``rows`` on the first data sheet."""
    wb = Workbook()
    wb.remove(wb.active)
    sheets = [
        [["fecha"], [date(2024, 10, 1)]],
        [_HEADER, *rows],
        [_HEADER],
        [_HEADER],
        [["Síntesis"]],
    ]
    for s in sheets:
        ws = wb.create_sheet()
        for row in s:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _servicio(nro: str, periodo_id: int, tipo_id: int) -> Servicio:
    return Servicio(
        nro_servicio=nro,
        codigo_radio="659",
        fecha=date(2024, 10, 15),
        dominio="ABC123",
        cod_productor=7,
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_id,
    )


async def _crear_periodo(uow, anio: int, mes: int, nombre: str):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


async def _crear_ts(uow, rama: str, nombre: str, codigo: str, categoria: str = "basico"):
    return await tipo_servicio.crear_tipo_servicio(
        uow, CreateTipoServicio(rama=rama, nombre=nombre, codigo=codigo, categoria=categoria)
    )


# --- Repository: reemplazar_por_periodo ---------------------------------------


def test_reemplazar_por_periodo_set_exacto():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "Automotores", "Básico", "659")
            await uow.servicios.add(_servicio("A1", p.id, ts.id))
            await uow.servicios.add(_servicio("A2", p.id, ts.id))
            await uow.servicios.reemplazar_por_periodo(
                p.id,
                [_servicio("B1", p.id, ts.id), _servicio("B2", p.id, ts.id)],
            )
            actuales = await uow.servicios.get_by_fields(periodo_id=p.id)
            assert {s.nro_servicio for s in actuales} == {"B1", "B2"}

    run_test(main)


def test_reemplazar_por_periodo_scope_otro_periodo():
    async def main():
        async with PostgresUoW() as uow:
            a = await _crear_periodo(uow, 2026, 1, "Ene")
            b = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "Automotores", "Básico", "659")
            await uow.servicios.add(_servicio("A1", a.id, ts.id))
            await uow.servicios.add(_servicio("B1", b.id, ts.id))
            await uow.servicios.reemplazar_por_periodo(
                a.id, [_servicio("A2", a.id, ts.id)]
            )
            a_rows = await uow.servicios.get_by_fields(periodo_id=a.id)
            b_rows = await uow.servicios.get_by_fields(periodo_id=b.id)
            assert {s.nro_servicio for s in a_rows} == {"A2"}
            assert {s.nro_servicio for s in b_rows} == {"B1"}

    run_test(main)


def test_reemplazar_por_periodo_empty_set():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "Automotores", "Básico", "659")
            await uow.servicios.add(_servicio("A1", p.id, ts.id))
            await uow.servicios.reemplazar_por_periodo(p.id, [])
            assert await uow.servicios.get_by_fields(periodo_id=p.id) == []

    run_test(main)


# --- Use case: importar_servicios ---------------------------------------------


def test_import_upsert_idempotente():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await _crear_ts(uow, "Automotores", "Básico", "659")
            filas = [
                ["S001", "15/10/2024", "ABC123", "659", "7"],
                ["S002", "16/10/2024", "XYZ789", "659", "8"],
            ]
            r1 = await servicio.importar_servicios(uow, p.id, _xlsx(filas), "upsert", rol=RolUsuario.ADMIN)
            assert r1 == {"creados": 2, "actualizados": 0, "eliminados": 0, "pendientes": []}
            r2 = await servicio.importar_servicios(uow, p.id, _xlsx(filas), "upsert", rol=RolUsuario.ADMIN)
            assert r2 == {"creados": 0, "actualizados": 2, "eliminados": 0, "pendientes": []}
            actuales = await uow.servicios.get_by_fields(periodo_id=p.id)
            assert len(actuales) == 2

    run_test(main)


def test_import_reemplazo_solo_target():
    async def main():
        async with PostgresUoW() as uow:
            a = await _crear_periodo(uow, 2026, 1, "Ene")
            b = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "Automotores", "Básico", "659")
            await uow.servicios.add(_servicio("OLD1", a.id, ts.id))
            await uow.servicios.add(_servicio("B1", b.id, ts.id))
            filas = [
                ["S001", "15/10/2024", "ABC123", "659", "7"],
                ["S002", "16/10/2024", "XYZ789", "659", "8"],
            ]
            r = await servicio.importar_servicios(uow, a.id, _xlsx(filas), "reemplazo", rol=RolUsuario.ADMIN)
            assert r == {"creados": 2, "actualizados": 0, "eliminados": 1, "pendientes": []}
            a_rows = await uow.servicios.get_by_fields(periodo_id=a.id)
            b_rows = await uow.servicios.get_by_fields(periodo_id=b.id)
            assert {s.nro_servicio for s in a_rows} == {"s001", "s002"}
            assert {s.nro_servicio for s in b_rows} == {"B1"}

    run_test(main)


def test_import_codigo_desconocido_importa_conocidas_y_reporta_pendientes():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await _crear_ts(uow, "Automotores", "Básico", "659")
            filas = [
                ["S001", "15/10/2024", "ABC123", "659", "7"],
                ["S002", "16/10/2024", "XYZ789", "61", "8"],  # codigo 61 sin tipo
                ["S003", "17/10/2024", "LMN456", "61", "9"],  # otro 61
            ]
            r = await servicio.importar_servicios(uow, p.id, _xlsx(filas), "upsert", rol=RolUsuario.ADMIN)
            assert r["creados"] == 1
            assert r["pendientes"] == [{"codigo": "61", "filas": 2}]
            actuales = await uow.servicios.get_by_fields(periodo_id=p.id)
            assert {s.nro_servicio for s in actuales} == {"s001"}

    run_test(main)


def test_import_reemplazo_con_pendientes_solo_reemplaza_conocidas():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "Automotores", "Básico", "659")
            await uow.servicios.add(_servicio("OLD1", p.id, ts.id))
            filas = [
                ["S001", "15/10/2024", "ABC123", "659", "7"],
                ["S002", "16/10/2024", "XYZ789", "61", "8"],
            ]
            r = await servicio.importar_servicios(uow, p.id, _xlsx(filas), "reemplazo", rol=RolUsuario.ADMIN)
            assert r["creados"] == 1
            assert r["eliminados"] == 1
            assert r["pendientes"] == [{"codigo": "61", "filas": 1}]
            actuales = await uow.servicios.get_by_fields(periodo_id=p.id)
            assert {s.nro_servicio for s in actuales} == {"s001"}

    run_test(main)


def test_import_sin_auto_cierre():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await _crear_ts(uow, "Automotores", "Básico", "659")
            filas = [["S001", "15/10/2024", "ABC123", "659", "7"]]
            await servicio.importar_servicios(uow, p.id, _xlsx(filas), "upsert", rol=RolUsuario.ADMIN)
            assert await uow.cierres.get_oficial(p.id) is None
            assert await uow.cierres.list() == []

    run_test(main)
