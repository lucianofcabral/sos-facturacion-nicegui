"""Integration tests for the Reportes dashboard read model (testcontainers Postgres).

Cubre: DB vacía devuelve ceros, conteo por tipo de servicio (incluido alias), y
el resumen del dashboard (KPIs + serie de periodos con cuadro de cierre).
"""

from __future__ import annotations

from datetime import date

from conftest import run_test
from src.application.use_cases import cierre as cierre_uc
from src.application.use_cases import periodo, tipo_servicio
from src.application.use_cases.reportes import resumen_dashboard
from src.domain.dto.create import CreatePeriodo, CreateTipoServicio
from src.domain.models.entities import Servicio
from src.infrastructure.adapters.uow import PostgresUoW


async def _tipo(uow, cat: str, cod: str, es_alias: bool = False):
    return await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores",
            nombre=cat,
            codigo=cod,
            categoria=cat,
            es_alias=es_alias,
        ),
    )


async def _periodo(uow, nombre: str, anio: int, mes: int):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


def _servicio(nro: str, pid: int, tid: int) -> Servicio:
    return Servicio(
        nro_servicio=nro,
        codigo_radio="659",
        fecha=date(2024, 1, 15),
        dominio="ABC123",
        cod_productor=1,
        periodo_id=pid,
        tipo_servicio_id=tid,
    )


def test_resumen_dashboard_vacio():
    async def main():
        async with PostgresUoW() as uow:
            r = await resumen_dashboard(uow)
        assert r.total_servicios == 0
        assert r.periodos_con_servicios == 0
        assert r.tipos_distintos == 0
        assert r.conteos_categoria == []
        assert r.conteos_tipo == []
        assert r.periodos == []

    run_test(main)


def test_conteo_por_tipo_incluye_alias():
    async def main():
        async with PostgresUoW() as uow:
            t_bas = await _tipo(uow, "basico", "659")
            t_legacy = await _tipo(uow, "basico", "61", es_alias=True)
            t_vip = await _tipo(uow, "vip", "658")
            p = await _periodo(uow, "Ene 2024", 2024, 1)
            await uow.servicios.add(_servicio("S1", p.id, t_bas.id))
            await uow.servicios.add(_servicio("S2", p.id, t_bas.id))
            await uow.servicios.add(_servicio("S3", p.id, t_legacy.id))
            await uow.servicios.add(_servicio("S4", p.id, t_vip.id))
            await uow.commit()
            conteos = await uow.servicios.conteo_por_tipo()

        por_codigo = {c.codigo: c for c in conteos}
        assert por_codigo["659"].total == 2
        assert por_codigo["61"].total == 1
        assert por_codigo["61"].es_alias is True
        assert por_codigo["658"].total == 1
        assert por_codigo["659"].es_alias is False
        assert len(conteos) == 3

    run_test(main)


def test_resumen_dashboard_kpis_y_cuadro():
    async def main():
        async with PostgresUoW() as uow:
            t_bas = await _tipo(uow, "basico", "659")
            t_vip = await _tipo(uow, "vip", "658")
            p = await _periodo(uow, "Ene 2024", 2024, 1)
            await uow.servicios.add(_servicio("S1", p.id, t_bas.id))
            await uow.servicios.add(_servicio("S2", p.id, t_bas.id))
            await uow.servicios.add(_servicio("S3", p.id, t_vip.id))
            await uow.commit()
            await cierre_uc.cerrar_periodo(uow, p.id, 0)
            r = await resumen_dashboard(uow)

        assert r.total_servicios == 3
        assert r.periodos_con_servicios == 1
        assert r.tipos_distintos == 2
        assert {c.codigo: c.total for c in r.conteos_tipo} == {"659": 2, "658": 1}

        # El periodo cerrado trae su cuadro de cierre con las claves del snapshot.
        assert len(r.periodos) == 1
        assert r.periodos[0].cerrado is True
        cuadro = r.periodos[0].cuadro
        assert cuadro is not None
        assert cuadro["servicios"]["total"] == 3
        assert cuadro["servicios"]["basico"] == 2
        assert cuadro["servicios"]["vip"] == 1
        assert cuadro["coef_uso"] == "0"
        assert "capitas" in cuadro
        assert "valores" in cuadro

    run_test(main)
