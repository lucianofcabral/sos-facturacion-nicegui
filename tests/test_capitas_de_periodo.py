"""Integration tests for the capitas-per-periodo read model (testcontainers)."""

from __future__ import annotations

from conftest import run_test
from src.application.use_cases import capita_periodo, periodo, tipo_servicio
from src.domain.dto.create import (
    CreateCapitaPeriodo,
    CreatePeriodo,
    CreateTipoServicio,
)
from src.infrastructure.adapters.uow import PostgresUoW


async def _base(uow):
    p = await periodo.crear_periodo(
        uow, CreatePeriodo(nombre="Ene 2026", anio=2026, mes=1)
    )
    t1 = await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores", nombre="Básico", codigo="659", categoria="basico"
        ),
    )
    t2 = await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores", nombre="VIP", codigo="658", categoria="vip"
        ),
    )
    return p, t1, t2


def test_listar_capitas_de_periodo_con_y_sin_fila():
    async def main():
        async with PostgresUoW() as uow:
            p, t1, t2 = await _base(uow)
            await capita_periodo.crear_capita_periodo(
                uow,
                CreateCapitaPeriodo(periodo_id=p.id, tipo_servicio_id=t1.id, capitas=10),
            )
            items = await capita_periodo.listar_capitas_de_periodo(uow, p.id)
            by_tipo = {i.tipo_servicio_id: i for i in items}
            assert set(by_tipo) == {t1.id, t2.id}
            assert by_tipo[t1.id].capitas == 10
            assert by_tipo[t1.id].tipo_nombre == "Básico"
            assert by_tipo[t2.id].capitas is None

    run_test(main)


def test_listar_capitas_de_periodo_sin_capitas_todas_none():
    async def main():
        async with PostgresUoW() as uow:
            p, _t1, _t2 = await _base(uow)
            items = await capita_periodo.listar_capitas_de_periodo(uow, p.id)
            assert len(items) == 2
            assert all(i.capitas is None for i in items)

    run_test(main)
