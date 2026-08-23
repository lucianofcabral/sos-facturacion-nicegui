"""Integration tests for the tipo-servicio metrics read model (testcontainers).

Covers services count, distinct cycles where the tipo appears (via servicio,
alicuota or capita), and first/last cycle ordering.
"""

from __future__ import annotations

from datetime import date

from conftest import run_test
from src.application.use_cases import periodo, tipo_servicio
from src.domain.dto.create import CreatePeriodo, CreateTipoServicio
from src.domain.models.entities import Alicuota, Servicio
from src.infrastructure.adapters.uow import PostgresUoW


async def _tipo(uow) -> tuple:
    ts = await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores", nombre="Básico", codigo="659", categoria="basico"
        ),
    )
    return ts


async def _periodo(uow, nombre: str, anio: int, mes: int):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


def _servicio(nro: str, periodo_id: int, tipo_id: int) -> Servicio:
    return Servicio(
        nro_servicio=nro,
        codigo_radio="659",
        fecha=date(2024, 1, 15),
        dominio="ABC123",
        cod_productor=1,
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_id,
    )


def test_metricas_servicios_y_ciclos():
    async def main():
        async with PostgresUoW() as uow:
            ts = await _tipo(uow)
            p1 = await _periodo(uow, "Ene 2024", 2024, 1)
            p2 = await _periodo(uow, "Feb 2025", 2025, 2)
            p3 = await _periodo(uow, "Mar 2026", 2026, 3)
            await uow.servicios.add(_servicio("S1", p1.id, ts.id))
            await uow.servicios.add(_servicio("S2", p2.id, ts.id))
            await uow.alicuotas.add(
                Alicuota(periodo_id=p3.id, tipo_servicio_id=ts.id, coeficiente=0.5, valor=10.0)
            )
            await uow.commit()
            m = await tipo_servicio.metricas_tipo_servicio(uow, ts.id)
            assert m.servicios_asociados == 2
            assert m.ciclos == 3
            assert m.primer_ciclo == "Ene 2024"
            assert m.ultimo_ciclo == "Mar 2026"

    run_test(main)


def test_metricas_sin_presencia():
    async def main():
        async with PostgresUoW() as uow:
            ts = await _tipo(uow)
            m = await tipo_servicio.metricas_tipo_servicio(uow, ts.id)
            assert m.servicios_asociados == 0
            assert m.ciclos == 0
            assert m.primer_ciclo is None
            assert m.ultimo_ciclo is None

    run_test(main)


def test_metricas_solo_alicuota_cuenta_ciclo():
    async def main():
        async with PostgresUoW() as uow:
            ts = await _tipo(uow)
            p1 = await _periodo(uow, "Ene 2024", 2024, 1)
            await uow.alicuotas.add(
                Alicuota(periodo_id=p1.id, tipo_servicio_id=ts.id, coeficiente=0.5, valor=10.0)
            )
            await uow.commit()
            m = await tipo_servicio.metricas_tipo_servicio(uow, ts.id)
            assert m.servicios_asociados == 0
            assert m.ciclos == 1
            assert m.primer_ciclo == "Ene 2024"
            assert m.ultimo_ciclo == "Ene 2024"

    run_test(main)
