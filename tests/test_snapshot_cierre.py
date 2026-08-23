"""Integration tests for snapshot persistence and síntesis (testcontainers).

Covers the repository layer (``get_oficiales_recientes``, Jsonb ``add``
override) and the closure use cases (snapshot population in both paths,
``armar_hoja_sintesis``).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from conftest import run_test
from src.application.use_cases import (
    alicuota,
    capita_periodo,
    cierre,
    periodo,
    servicio,
    tipo_servicio,
)
from src.domain.dto.create import (
    CreateAlicuota,
    CreateCapitaPeriodo,
    CreatePeriodo,
    CreateServicio,
    CreateTipoServicio,
)
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.models.entities import Cierre
from src.infrastructure.adapters.uow import PostgresUoW


async def _crear_periodo(uow, anio: int, mes: int, nombre: str):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


async def _crear_ts(uow, rama: str, nombre: str):
    return await tipo_servicio.crear_tipo_servicio(
        uow, CreateTipoServicio(rama=rama, nombre=nombre)
    )


async def _crear_alicuota(uow, periodo_id, tipo_servicio_id, coeficiente, valor):
    return await alicuota.crear_alicuota(
        uow,
        CreateAlicuota(
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
            coeficiente=coeficiente,
            valor=valor,
        ),
    )


async def _crear_capita(uow, periodo_id, tipo_servicio_id, capitas):
    return await capita_periodo.crear_capita_periodo(
        uow,
        CreateCapitaPeriodo(
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
            capitas=capitas,
        ),
    )


async def _crear_servicio(
    uow, nro, periodo_id, tipo_servicio_id, *, fecha=None, codigo_radio="R1"
):
    return await servicio.crear_servicio(
        uow,
        CreateServicio(
            nro_servicio=nro,
            codigo_radio=codigo_radio,
            fecha=fecha or date(2026, 1, 15),
            dominio="ABC123",
            cod_productor=7,
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
        ),
    )


def _cierre(periodo_id, version, estado, origen, aumento=Decimal("0"), snapshot=None):
    return Cierre(
        periodo_id=periodo_id,
        version=version,
        estado=estado,
        origen=origen,
        aumento=aumento,
        snapshot=snapshot,
    )


# --- Repository: get_oficiales_recientes ---------------------------------------


def test_get_oficiales_recientes_desc_and_limit():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            abr = await _crear_periodo(uow, 2026, 4, "Abr")
            may = await _crear_periodo(uow, 2026, 5, "May")
            for p in (ene, feb, mar, abr):
                await uow.cierres.add(
                    _cierre(p.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
                )
            recientes = await uow.cierres.get_oficiales_recientes(may.id, limit=2)
            assert [c.periodo_id for c in recientes] == [abr.id, mar.id]

    run_test(main)


def test_get_oficiales_recientes_excludes_target():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            for p in (ene, feb, mar):
                await uow.cierres.add(
                    _cierre(p.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
                )
            recientes = await uow.cierres.get_oficiales_recientes(mar.id, limit=10)
            assert [c.periodo_id for c in recientes] == [feb.id, ene.id]

    run_test(main)


def test_get_oficiales_recientes_only_oficial():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            abr = await _crear_periodo(uow, 2026, 4, "Abr")
            await uow.cierres.add(
                _cierre(ene.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
            )
            await uow.cierres.add(
                _cierre(feb.id, 1, EstadoCierre.NO_OFICIAL, OrigenCierre.MANUAL)
            )
            await uow.cierres.add(
                _cierre(mar.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
            )
            recientes = await uow.cierres.get_oficiales_recientes(abr.id, limit=10)
            assert [c.periodo_id for c in recientes] == [mar.id, ene.id]

    run_test(main)


def test_get_oficiales_recientes_year_boundary():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            for p in (dic, ene):
                await uow.cierres.add(
                    _cierre(p.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
                )
            recientes = await uow.cierres.get_oficiales_recientes(feb.id, limit=10)
            assert [c.periodo_id for c in recientes] == [ene.id, dic.id]

    run_test(main)


# --- Repository: add/get snapshot round-trip (Jsonb) ---------------------------


def test_add_get_snapshot_roundtrip_jsonb():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            snapshot = {
                "servicios_total": [],
                "sintesis": {
                    "total": Decimal("2150.00"),
                    "fecha": date(2026, 1, 15),
                    "n": 3,
                },
            }
            creado = await uow.cierres.add(
                _cierre(
                    ene.id,
                    1,
                    EstadoCierre.OFICIAL,
                    OrigenCierre.MANUAL,
                    snapshot=snapshot,
                )
            )
            leido = await uow.cierres.get(creado.id)
            assert leido.snapshot == {
                "servicios_total": [],
                "sintesis": {"total": "2150.00", "fecha": "2026-01-15", "n": 3},
            }

    run_test(main)


def test_add_snapshot_none_still_works():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            creado = await uow.cierres.add(
                _cierre(ene.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
            )
            assert creado.snapshot is None

    run_test(main)
