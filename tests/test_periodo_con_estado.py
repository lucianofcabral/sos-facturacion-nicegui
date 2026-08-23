"""Integration tests for the periodos con estado read model (testcontainers).

Covers descending order, closed/total derivation from the official cierre
snapshot, and open periods with no total.
"""

from __future__ import annotations

from decimal import Decimal

from conftest import run_test
from src.application.use_cases import periodo
from src.domain.dto.create import CreatePeriodo
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.models.entities import Cierre
from src.infrastructure.adapters.uow import PostgresUoW


def _cierre(periodo_id: int, total: str) -> Cierre:
    return Cierre(
        periodo_id=periodo_id,
        version=1,
        estado=EstadoCierre.OFICIAL,
        origen=OrigenCierre.MANUAL,
        aumento=Decimal("0"),
        snapshot={"sintesis": {"total_a_pagar": total}},
    )


def test_listar_periodos_con_estado_orden_desc():
    async def main():
        async with PostgresUoW() as uow:
            await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene", anio=2025, mes=1))
            await periodo.crear_periodo(uow, CreatePeriodo(nombre="Feb", anio=2026, mes=2))
            await periodo.crear_periodo(uow, CreatePeriodo(nombre="Mar", anio=2024, mes=3))
            items = await periodo.listar_periodos_con_estado(uow)
            assert [(i.anio, i.mes) for i in items] == [(2026, 2), (2025, 1), (2024, 3)]
            assert all(i.cerrado is False for i in items)
            assert all(i.total is None for i in items)

    run_test(main)


def test_listar_periodos_con_estado_cerrado_con_total():
    async def main():
        async with PostgresUoW() as uow:
            p = await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene", anio=2025, mes=1))
            await uow.cierres.add(_cierre(p.id, "1234.56"))
            await uow.commit()
            items = await periodo.listar_periodos_con_estado(uow)
            assert len(items) == 1
            assert items[0].cerrado is True
            assert items[0].total == Decimal("1234.56")

    run_test(main)


def test_listar_periodos_con_estado_abierto_sin_total():
    async def main():
        async with PostgresUoW() as uow:
            await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene", anio=2025, mes=1))
            items = await periodo.listar_periodos_con_estado(uow)
            assert len(items) == 1
            assert items[0].cerrado is False
            assert items[0].total is None

    run_test(main)
