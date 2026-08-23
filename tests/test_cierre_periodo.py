"""Integration tests for Cierre de Periodo (testcontainers Postgres).

Covers the repository layer (previous-period resolution, versioning, atomic
batch replace, single-oficial invariant) and the ``cerrar_periodo`` use case.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from psycopg.errors import UniqueViolation

from conftest import run_test
from src.application.use_cases import alicuota, cierre, periodo, tipo_servicio
from src.domain.dto.create import CreateAlicuota, CreatePeriodo, CreateTipoServicio
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import PeriodoAlreadyClosedError, RecalculoInvalidoError
from src.domain.models.entities import Alicuota, Cierre
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


def _oficial(periodo_id: int, version: int) -> Cierre:
    return Cierre(
        periodo_id=periodo_id,
        version=version,
        estado=EstadoCierre.OFICIAL,
        origen=OrigenCierre.MANUAL,
        aumento=Decimal("0"),
    )


def test_get_previous_none_when_no_earlier_period():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene-2026")
            assert await uow.periodos.get_previous(p.anio, p.mes) is None

    run_test(main)


def test_get_previous_strictly_earlier():
    async def main():
        async with PostgresUoW() as uow:
            p_ene = await _crear_periodo(uow, 2026, 1, "Ene")
            p_feb = await _crear_periodo(uow, 2026, 2, "Feb")
            await _crear_periodo(uow, 2026, 3, "Mar")
            assert (await uow.periodos.get_previous(2026, 3)).id == p_feb.id
            assert (await uow.periodos.get_previous(2026, 2)).id == p_ene.id

    run_test(main)


def test_next_version_increments():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            assert await uow.cierres.next_version(p.id) == 1
            await uow.cierres.add(_oficial(p.id, 1))
            assert await uow.cierres.next_version(p.id) == 2

    run_test(main)


def test_reemplazar_por_periodo_diff():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts_a = await _crear_ts(uow, "A", "A")
            ts_b = await _crear_ts(uow, "B", "B")
            ts_c = await _crear_ts(uow, "C", "C")
            ts_d = await _crear_ts(uow, "D", "D")
            await _crear_alicuota(uow, p.id, ts_a.id, 0.5, 10.0)
            await _crear_alicuota(uow, p.id, ts_d.id, 0.5, 40.0)
            nuevo = [
                Alicuota(periodo_id=p.id, tipo_servicio_id=ts_a.id, coeficiente=0.5, valor=11.0),
                Alicuota(periodo_id=p.id, tipo_servicio_id=ts_b.id, coeficiente=0.5, valor=20.0),
                Alicuota(periodo_id=p.id, tipo_servicio_id=ts_c.id, coeficiente=0.5, valor=30.0),
            ]
            await uow.alicuotas.reemplazar_por_periodo(p.id, nuevo)
            actuales = await uow.alicuotas.get_by_keys(periodo_id=p.id)
            by_id = {a.tipo_servicio_id: a.valor for a in actuales}
            assert by_id == {ts_a.id: 11.0, ts_b.id: 20.0, ts_c.id: 30.0}

    run_test(main)


def test_reemplazar_por_periodo_empty_set():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, p.id, ts.id, 0.5, 10.0)
            await uow.alicuotas.reemplazar_por_periodo(p.id, [])
            assert (await uow.alicuotas.get_by_keys(periodo_id=p.id)) == []

    run_test(main)


def test_second_oficial_violates_unique():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await uow.cierres.add(_oficial(p.id, 1))
            async with uow._conn.cursor() as cur:
                with pytest.raises(UniqueViolation):
                    await cur.execute(
                        "INSERT INTO cierre (periodo_id, version, estado, origen, aumento) "
                        "VALUES (%s, %s, 'oficial', 'manual', %s)",
                        (p.id, 2, Decimal("0")),
                    )

    run_test(main)


def test_cerrar_first_period_keeps_manual_alicuotas():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, p.id, ts.id, 0.5, 77.0)
            c = await cierre.cerrar_periodo(uow, p.id, Decimal("10"))
            assert c.estado == EstadoCierre.OFICIAL
            assert c.origen == OrigenCierre.MANUAL
            assert c.version == 1
            actuales = await uow.alicuotas.get_by_keys(periodo_id=p.id)
            assert [a.valor for a in actuales] == [77.0]

    run_test(main)


def test_cerrar_recalculates_from_previous():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts_a = await _crear_ts(uow, "A", "A")
            ts_b = await _crear_ts(uow, "B", "B")
            ts_c = await _crear_ts(uow, "C", "C")
            ts_d = await _crear_ts(uow, "D", "D")
            await _crear_alicuota(uow, prev.id, ts_a.id, 0.5, 100.0)
            await _crear_alicuota(uow, prev.id, ts_b.id, 0.5, 200.0)
            await _crear_alicuota(uow, prev.id, ts_c.id, 0.5, 300.0)
            await _crear_alicuota(uow, target.id, ts_a.id, 0.5, 999.0)
            await _crear_alicuota(uow, target.id, ts_d.id, 0.5, 400.0)
            c = await cierre.cerrar_periodo(uow, target.id, Decimal("10"))
            assert c.version == 1
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            by_id = {a.tipo_servicio_id: a.valor for a in actuales}
            assert by_id == {ts_a.id: 110.0, ts_b.id: 220.0, ts_c.id: 330.0}

    run_test(main)


def test_cerrar_rebaja():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, prev.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, target.id, Decimal("-10"))
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            assert [a.valor for a in actuales] == [90.0]

    run_test(main)


def test_cerrar_double_close_rejected():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            await cierre.cerrar_periodo(uow, p.id, Decimal("0"))
            with pytest.raises(PeriodoAlreadyClosedError):
                await cierre.cerrar_periodo(uow, p.id, Decimal("5"))

    run_test(main)


def test_cerrar_atomic_on_recalc_error():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts_a = await _crear_ts(uow, "A", "A")
            ts_b = await _crear_ts(uow, "B", "B")
            ts_d = await _crear_ts(uow, "D", "D")
            await _crear_alicuota(uow, prev.id, ts_a.id, 0.5, 100.0)
            await _crear_alicuota(uow, prev.id, ts_b.id, 0.5, 0.01)
            await _crear_alicuota(uow, target.id, ts_d.id, 0.5, 50.0)
            with pytest.raises(RecalculoInvalidoError):
                await cierre.cerrar_periodo(uow, target.id, Decimal("-99"))
            assert await uow.cierres.get_oficial(target.id) is None
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            assert {a.tipo_servicio_id: a.valor for a in actuales} == {ts_d.id: 50.0}

    run_test(main)


def test_cerrar_post_rounding_zero_persists_nothing():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "A", "A")
            await _crear_alicuota(uow, prev.id, ts.id, 0.5, 0.01)
            await _crear_alicuota(uow, target.id, ts.id, 0.5, 50.0)
            with pytest.raises(RecalculoInvalidoError):
                await cierre.cerrar_periodo(uow, target.id, Decimal("-99"))
            assert await uow.cierres.get_oficial(target.id) is None
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            assert [a.valor for a in actuales] == [50.0]

    run_test(main)
