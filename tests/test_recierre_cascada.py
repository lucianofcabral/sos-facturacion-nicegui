"""Integration tests for re-cierre en cascada (testcontainers Postgres).

Covers the repository layer (``get_following``, ``demote_oficial``) and the
``generar_nuevo_cierre`` use case, including the cascade shared with
``cerrar_periodo``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from conftest import run_test
from src.application.use_cases import alicuota, cierre, periodo, tipo_servicio
from src.domain.dto.create import CreateAlicuota, CreatePeriodo, CreateTipoServicio
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import PeriodoNotClosedError, RecalculoInvalidoError
from src.domain.models.entities import Cierre
from src.infrastructure.adapters.uow import PostgresUoW


async def _crear_periodo(uow, anio: int, mes: int, nombre: str):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


async def _crear_ts(uow, rama: str, nombre: str):
    return await tipo_servicio.crear_tipo_servicio(
        uow, CreateTipoServicio(rama=rama, nombre=nombre, codigo=nombre)
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


def _cierre(periodo_id, version, estado, origen, aumento=Decimal("0"), motivo=None):
    return Cierre(
        periodo_id=periodo_id,
        version=version,
        estado=estado,
        origen=origen,
        aumento=aumento,
        motivo=motivo,
    )


async def _alicuota_vals(uow, periodo_id: int) -> dict[int, float]:
    actuales = await uow.alicuotas.get_by_keys(periodo_id=periodo_id)
    return {a.tipo_servicio_id: a.valor for a in actuales}


# --- Repository: get_following -------------------------------------------------


def test_get_following_none_later():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 12, "Dic")
            assert await uow.periodos.get_following(p.anio, p.mes) == []

    run_test(main)


def test_get_following_asc_multi():
    async def main():
        async with PostgresUoW() as uow:
            await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            await _crear_periodo(uow, 2026, 3, "Mar")
            await _crear_periodo(uow, 2026, 4, "Abr")
            sig = await uow.periodos.get_following(feb.anio, feb.mes)
            assert [p.nombre for p in sig] == ["Mar", "Abr"]

    run_test(main)


def test_get_following_year_boundary():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2026, 12, "Dic")
            await _crear_periodo(uow, 2027, 1, "Ene27")
            sig = await uow.periodos.get_following(dic.anio, dic.mes)
            assert [p.nombre for p in sig] == ["Ene27"]

    run_test(main)


def test_get_following_strictly_greater():
    async def main():
        async with PostgresUoW() as uow:
            await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            sig = await uow.periodos.get_following(feb.anio, feb.mes)
            assert sig == []

    run_test(main)


# --- Repository: demote_oficial ------------------------------------------------


def test_demote_oficial_demotes_and_keeps_history():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await uow.cierres.add(_cierre(p.id, 1, EstadoCierre.NO_OFICIAL, OrigenCierre.MANUAL))
            await uow.cierres.add(_cierre(p.id, 2, EstadoCierre.OFICIAL, OrigenCierre.MANUAL))
            await uow.cierres.demote_oficial(p.id)
            assert await uow.cierres.get_oficial(p.id) is None
            historial = await uow.cierres.list()
            assert len(historial) == 2
            v2 = next(c for c in historial if c.version == 2)
            assert v2.estado == EstadoCierre.NO_OFICIAL

    run_test(main)


def test_demote_oficial_no_oficial_raises():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            with pytest.raises(PeriodoNotClosedError):
                await uow.cierres.demote_oficial(p.id)

    run_test(main)


# --- Use case: generar_nuevo_cierre -------------------------------------------


def test_generar_no_oficial_raises_nothing_persists():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            with pytest.raises(PeriodoNotClosedError):
                await cierre.generar_nuevo_cierre(uow, p.id, Decimal("10"))
            assert await uow.cierres.get_oficial(p.id) is None
            assert await uow.cierres.list() == []

    run_test(main)


def test_generar_reclose_v3_v4():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await uow.cierres.add(_cierre(p.id, 1, EstadoCierre.NO_OFICIAL, OrigenCierre.MANUAL))
            await uow.cierres.add(_cierre(p.id, 2, EstadoCierre.NO_OFICIAL, OrigenCierre.MANUAL))
            await uow.cierres.add(
                _cierre(p.id, 3, EstadoCierre.OFICIAL, OrigenCierre.MANUAL, aumento=Decimal("10"))
            )
            nuevo = await cierre.generar_nuevo_cierre(uow, p.id, Decimal("20"), motivo="ajuste")
            assert nuevo.version == 4
            assert nuevo.estado == EstadoCierre.OFICIAL
            assert nuevo.origen == OrigenCierre.MANUAL
            assert nuevo.motivo == "ajuste"
            assert nuevo.aumento == Decimal("20")
            oficial = await uow.cierres.get_oficial(p.id)
            assert oficial.id == nuevo.id
            historial = await uow.cierres.list()
            assert len(historial) == 4
            v3 = next(c for c in historial if c.version == 3)
            assert v3.estado == EstadoCierre.NO_OFICIAL

    run_test(main)


def test_generar_first_period_keeps_manual_set():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, p.id, ts.id, 0.5, 77.0)
            await cierre.cerrar_periodo(uow, p.id, Decimal("0"))
            await cierre.generar_nuevo_cierre(uow, p.id, Decimal("15"))
            assert await _alicuota_vals(uow, p.id) == {ts.id: 77.0}
            oficial = await uow.cierres.get_oficial(p.id)
            assert oficial.version == 2

    run_test(main)


def test_generar_unchanged_skips_cascade():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, ene.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, ene.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, feb.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, mar.id, Decimal("10"))
            await cierre.generar_nuevo_cierre(uow, feb.id, Decimal("10"))
            assert (await uow.cierres.get_oficial(feb.id)).version == 2
            mar_oficial = await uow.cierres.get_oficial(mar.id)
            assert mar_oficial.version == 1
            assert mar_oficial.origen == OrigenCierre.MANUAL
            assert await _alicuota_vals(uow, mar.id) == {ts.id: 121.0}

    run_test(main)


def test_generar_chain_factors_and_own_aumento():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            abr = await _crear_periodo(uow, 2026, 4, "Abr")
            ts_a = await _crear_ts(uow, "A", "A")
            ts_b = await _crear_ts(uow, "B", "B")
            await _crear_alicuota(uow, ene.id, ts_a.id, 0.5, 100.0)
            await _crear_alicuota(uow, ene.id, ts_b.id, 0.5, 200.0)
            await cierre.cerrar_periodo(uow, ene.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, feb.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, mar.id, Decimal("20"))
            await cierre.cerrar_periodo(uow, abr.id, Decimal("5"))
            await cierre.generar_nuevo_cierre(uow, feb.id, Decimal("30"))
            assert await _alicuota_vals(uow, feb.id) == {ts_a.id: 130.0, ts_b.id: 260.0}
            assert await _alicuota_vals(uow, mar.id) == {ts_a.id: 156.0, ts_b.id: 312.0}
            assert await _alicuota_vals(uow, abr.id) == {ts_a.id: 163.8, ts_b.id: 327.6}
            mar_of = await uow.cierres.get_oficial(mar.id)
            assert mar_of.version == 2
            assert mar_of.origen == OrigenCierre.CASCADA
            assert mar_of.motivo == "cascada por Feb"
            assert mar_of.aumento == Decimal("20")
            abr_of = await uow.cierres.get_oficial(abr.id)
            assert abr_of.version == 2
            assert abr_of.origen == OrigenCierre.CASCADA
            assert abr_of.motivo == "cascada por Feb"
            assert abr_of.aumento == Decimal("5")

    run_test(main)


def test_generar_last_period_no_cascade():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, dic.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, dic.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, ene.id, Decimal("10"))
            await cierre.generar_nuevo_cierre(uow, ene.id, Decimal("20"))
            assert (await uow.cierres.get_oficial(ene.id)).version == 2
            assert await _alicuota_vals(uow, ene.id) == {ts.id: 120.0}

    run_test(main)


def test_generar_gap_breaks():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")  # gap: sin cierre
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, dic.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, dic.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, ene.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, mar.id, Decimal("10"))
            await cierre.generar_nuevo_cierre(uow, ene.id, Decimal("20"))
            assert await _alicuota_vals(uow, ene.id) == {ts.id: 120.0}
            assert await uow.cierres.get_oficial(feb.id) is None
            mar_of = await uow.cierres.get_oficial(mar.id)
            assert mar_of.version == 1
            assert mar_of.origen == OrigenCierre.MANUAL
            assert await _alicuota_vals(uow, mar.id) == {}

    run_test(main)


def test_generar_midchain_recalc_error_rolls_back():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            ts_a = await _crear_ts(uow, "A", "A")
            ts_b = await _crear_ts(uow, "B", "B")
            await _crear_alicuota(uow, dic.id, ts_a.id, 0.5, 100.0)
            await _crear_alicuota(uow, dic.id, ts_b.id, 0.5, 200.0)
            await cierre.cerrar_periodo(uow, dic.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, ene.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, feb.id, Decimal("-99.99"))
        async with PostgresUoW() as uow:
            with pytest.raises(RecalculoInvalidoError):
                await cierre.generar_nuevo_cierre(uow, ene.id, Decimal("-90"))
        async with PostgresUoW() as uow:
            ene_of = await uow.cierres.get_oficial(ene.id)
            assert ene_of.version == 1
            assert ene_of.aumento == Decimal("10")
            assert await _alicuota_vals(uow, ene.id) == {ts_a.id: 110.0, ts_b.id: 220.0}
            feb_of = await uow.cierres.get_oficial(feb.id)
            assert feb_of.version == 1
            assert feb_of.origen == OrigenCierre.MANUAL

    run_test(main)


def test_cerrar_out_of_order_cascades():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            mar = await _crear_periodo(uow, 2026, 3, "Mar")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, dic.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, dic.id, Decimal("0"))
            # ene queda con alicuotas manuales desactualizadas y sin cierre
            await _crear_alicuota(uow, ene.id, ts.id, 0.5, 999.0)
            # cierres fuera de orden: feb y mar se cierran antes que ene
            await cierre.cerrar_periodo(uow, feb.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, mar.id, Decimal("10"))
            # cerrar ene en orden tardío: debe cascadear feb y mar
            await cierre.cerrar_periodo(uow, ene.id, Decimal("10"))
            assert await _alicuota_vals(uow, ene.id) == {ts.id: 110.0}
            assert (await uow.cierres.get_oficial(ene.id)).version == 1
            feb_of = await uow.cierres.get_oficial(feb.id)
            assert feb_of.version == 2
            assert feb_of.origen == OrigenCierre.CASCADA
            assert await _alicuota_vals(uow, feb.id) == {ts.id: 121.0}
            mar_of = await uow.cierres.get_oficial(mar.id)
            assert mar_of.version == 2
            assert mar_of.origen == OrigenCierre.CASCADA
            assert await _alicuota_vals(uow, mar.id) == {ts.id: 133.1}

    run_test(main)
