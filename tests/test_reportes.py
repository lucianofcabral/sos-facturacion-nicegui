"""Integration tests for the Reportes read models (testcontainers Postgres).

Cubre: DB vacía devuelve ceros sin error, conteo agrupado por categoria,
orden y límite de top productores, y derivación de años distintos.
"""

from __future__ import annotations

from datetime import date

from conftest import run_test
from src.application.use_cases import periodo, tipo_servicio
from src.application.use_cases.reportes import resumen_reportes
from src.domain.dto.create import CreatePeriodo, CreateTipoServicio
from src.domain.models.entities import Servicio
from src.infrastructure.adapters.uow import PostgresUoW


async def _tipo(uow, cat: str, cod: str):
    return await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(rama="Automotores", nombre=cat, codigo=cod, categoria=cat),
    )


async def _periodo(uow, nombre: str, anio: int, mes: int):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


def _servicio(nro: str, pid: int, tid: int, productor: int) -> Servicio:
    return Servicio(
        nro_servicio=nro,
        codigo_radio="659",
        fecha=date(2024, 1, 15),
        dominio="ABC123",
        cod_productor=productor,
        periodo_id=pid,
        tipo_servicio_id=tid,
    )


def test_vacio_devuelve_ceros():
    async def main():
        async with PostgresUoW() as uow:
            r = await resumen_reportes(uow)
        assert r.total_servicios == 0
        assert r.periodos_con_servicios == 0
        assert r.productores_distintos == 0
        assert r.tipos_distintos == 0
        assert r.conteos_categoria == []
        assert r.top_productores == []

    run_test(main)


def test_conteo_por_categoria():
    async def main():
        async with PostgresUoW() as uow:
            t_bas = await _tipo(uow, "basico", "659")
            t_vip = await _tipo(uow, "vip", "658")
            p = await _periodo(uow, "Ene 2024", 2024, 1)
            await uow.servicios.add(_servicio("S1", p.id, t_bas.id, 1))
            await uow.servicios.add(_servicio("S2", p.id, t_bas.id, 2))
            await uow.servicios.add(_servicio("S3", p.id, t_vip.id, 3))
            await uow.commit()
            r = await resumen_reportes(uow)

        assert r.total_servicios == 3
        assert r.periodos_con_servicios == 1
        por_cat = {
            (c.anio, c.mes, c.categoria.value): c.total for c in r.conteos_categoria
        }
        assert por_cat[(2024, 1, "basico")] == 2
        assert por_cat[(2024, 1, "vip")] == 1

    run_test(main)


def test_top_productores_orden_y_limite():
    async def main():
        async with PostgresUoW() as uow:
            t = await _tipo(uow, "basico", "659")
            p = await _periodo(uow, "Ene 2024", 2024, 1)
            for i in range(3):
                await uow.servicios.add(_servicio(f"A{i}", p.id, t.id, 1))
            for i in range(1):
                await uow.servicios.add(_servicio(f"B{i}", p.id, t.id, 2))
            for i in range(5):
                await uow.servicios.add(_servicio(f"C{i}", p.id, t.id, 3))
            await uow.commit()
            top = await uow.servicios.top_productores(limite=2)

        assert [pr.cod_productor for pr in top] == [3, 1]
        assert top[0].total == 5
        assert top[1].total == 3
        assert len(top) == 2

    run_test(main)


def test_anios_distintos():
    async def main():
        async with PostgresUoW() as uow:
            t = await _tipo(uow, "basico", "659")
            p1 = await _periodo(uow, "Ene 2024", 2024, 1)
            p2 = await _periodo(uow, "Feb 2025", 2025, 2)
            await uow.servicios.add(_servicio("S1", p1.id, t.id, 1))
            await uow.servicios.add(_servicio("S2", p2.id, t.id, 1))
            await uow.commit()
            r = await resumen_reportes(uow)

        anios = {c.anio for c in r.conteos_categoria}
        assert anios == {2024, 2025}

    run_test(main)
