"""Integration tests for the historical seed (testcontainers Postgres).

Uses a small fixture workbook (4 months, 6 tipos, a subset coef ladder, one
double-aumento month and one 0% row) instead of the full 136-month Panel.xlsm.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from conftest import run_test
from scripts.seed_historico import SeedHistoricoError, ejecutar_seed
from src.application.services.panel_historico import ParserPanelHistorico
from src.domain.enums import EstadoCierre
from src.infrastructure.adapters.uow import PostgresUoW

# Fixture sintesis values per (anio, mes) → keeps assertions deterministic.
_SINTESIS = {
    (2014, 7): (100, 200, 300, 10, 20, 30, 1, 2, 3),
    (2014, 8): (110, 210, 310, 11, 21, 31, 4, 5, 6),
    (2014, 9): (120, 220, 320, 12, 22, 32, 7, 8, 9),
    (2014, 10): (130, 230, 330, 13, 23, 33, 10, 11, 12),
}


def _build_xlsx() -> BytesIO:
    wb = Workbook()
    wb.remove(wb.active)

    ws = wb.create_sheet("Inicial")
    ws.append(["Indice", "idPrestacion", "corta", "larga", "Valor"])
    bases = {1: Decimal("8.94"), 2: Decimal("10.84"), 3: Decimal("12.83")}
    for prest, base in bases.items():
        for coef in (Decimal("0.03"), Decimal("0.04"), Decimal("0.05")):
            valor = (base * coef / Decimal("0.03")).quantize(Decimal("0.01"))
            ws.append([float(coef), prest, "corta", "larga", float(valor)])

    ws = wb.create_sheet("SintesisH")
    ws.append(
        [
            "Periodo", "c_basico", "c_completo", "c_vip", "s_basico",
            "s_completo", "s_vip", "r_87", "r_89", "r_90", "coef", "coef minimo",
        ]
    )
    for (anio, mes), row in _SINTESIS.items():
        ws.append([date(anio, mes, 1), *row, 0.0, 0.0])

    ws = wb.create_sheet("Aumentos")
    ws.append(["Fecha", "Aumento"])
    ws.append([date(2014, 8, 1), 0])  # 0% no-op
    ws.append([date(2014, 9, 12), 10])
    ws.append([date(2014, 10, 1), 5])  # double month: 5 then 10
    ws.append([date(2014, 10, 17), 10])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _datos():
    return ParserPanelHistorico().leer(_build_xlsx())


def test_seed_writes_correct_counts():
    async def main():
        resultado = await ejecutar_seed(_datos())
        assert resultado["tipos"] == 6
        assert resultado["periodos"] == 4
        assert resultado["alicuotas"] == 9
        assert resultado["capitas"] == 24
        assert resultado["aumentos"] == 4

        async with PostgresUoW() as uow:
            tipos = await uow.tipos_servicio.list()
            assert len(tipos) == 6
            by_codigo = {t.codigo: t for t in tipos}
            assert set(by_codigo) == {"659", "660", "658", "87", "89", "90"}
            assert by_codigo["659"].nombre == "Básico"
            assert by_codigo["659"].rama == "Automotores"
            assert by_codigo["659"].categoria.value == "basico"
            assert by_codigo["658"].categoria.value == "vip"
            assert by_codigo["87"].nombre == "Rama 87"
            assert by_codigo["87"].rama == "Ramas Varias"
            assert by_codigo["87"].categoria.value == "rama_87"

            periodos = await uow.periodos.list()
            assert len(periodos) == 4
            nombres = [p.nombre for p in sorted(periodos, key=lambda p: (p.anio, p.mes))]
            assert nombres == [
                "JULIO 2014", "AGOSTO 2014", "SEPTIEMBRE 2014", "OCTUBRE 2014",
            ]

            jul = (await uow.periodos.get_by_anio_mes(2014, 7))[0]
            assert len(await uow.alicuotas.get_by_keys(periodo_id=jul.id)) == 9
            assert len(await uow.capitas_periodo.list()) == 24
            assert len(await uow.cierres.list()) == 5

    run_test(main)


def test_seed_double_month_two_versions():
    async def main():
        await ejecutar_seed(_datos())
        async with PostgresUoW() as uow:
            oct = (await uow.periodos.get_by_anio_mes(2014, 10))[0]
            oct_cierres = [c for c in await uow.cierres.list() if c.periodo_id == oct.id]
            assert len(oct_cierres) == 2
            by_version = {c.version: c for c in oct_cierres}
            assert by_version[1].estado == EstadoCierre.NO_OFICIAL
            assert by_version[1].aumento == Decimal("5")
            assert by_version[2].estado == EstadoCierre.OFICIAL
            assert by_version[2].aumento == Decimal("10")

    run_test(main)


def test_seed_snapshot_carries_injected_counts():
    async def main():
        await ejecutar_seed(_datos())
        async with PostgresUoW() as uow:
            jul = (await uow.periodos.get_by_anio_mes(2014, 7))[0]
            oficial = await uow.cierres.get_oficial(jul.id)
            sintesis = oficial.snapshot["sintesis"]
            # servicio table is empty: counts come from injected s_*
            assert sintesis["servicios"]["basico"] == 10
            assert sintesis["servicios"]["completo"] == 20
            assert sintesis["servicios"]["vip"] == 30
            assert sintesis["servicios"]["total"] == 60

    run_test(main)


def test_seed_zero_month_noop():
    async def main():
        await ejecutar_seed(_datos())
        async with PostgresUoW() as uow:
            jul = (await uow.periodos.get_by_anio_mes(2014, 7))[0]
            ago = (await uow.periodos.get_by_anio_mes(2014, 8))[0]
            jul_vals = {a.coeficiente: a.valor for a in await uow.alicuotas.get_by_keys(periodo_id=jul.id)}
            ago_vals = {a.coeficiente: a.valor for a in await uow.alicuotas.get_by_keys(periodo_id=ago.id)}
            assert ago_vals == jul_vals  # 0% aumento leaves values unchanged

    run_test(main)


def test_seed_second_run_aborts():
    async def main():
        await ejecutar_seed(_datos())
        with pytest.raises(SeedHistoricoError):
            await ejecutar_seed(_datos())

    run_test(main)


def test_seed_dry_run_writes_zero():
    async def main():
        resultado = await ejecutar_seed(_datos(), dry_run=True)
        assert resultado["dry_run"] is True
        assert resultado["tipos"] == 6
        assert resultado["periodos"] == 4
        async with PostgresUoW() as uow:
            assert await uow.periodos.list() == []
            assert await uow.tipos_servicio.list() == []

    run_test(main)
