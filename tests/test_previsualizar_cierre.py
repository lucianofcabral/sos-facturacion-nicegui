"""Integration tests for ``previsualizar_cierre`` (testcontainers Postgres).

Mirrors ``test_cierre_periodo.py``: the preview is a READ-ONLY use case that
returns the síntesis cuadro without persisting or committing, and must equal
the snapshot the closure would persist for identical inputs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

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
from src.domain.enums import RolUsuario
from src.infrastructure.adapters.uow import PostgresUoW


async def _crear_periodo(uow, anio: int, mes: int, nombre: str):
    return await periodo.crear_periodo(
        uow, CreatePeriodo(nombre=nombre, anio=anio, mes=mes)
    )


async def _crear_ts(uow, rama: str, nombre: str, categoria: str = "basico"):
    return await tipo_servicio.crear_tipo_servicio(
        uow, CreateTipoServicio(rama=rama, nombre=nombre, codigo=nombre, categoria=categoria)
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
        rol=RolUsuario.ADMIN,
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


async def _crear_servicio(uow, nro, periodo_id, tipo_servicio_id):
    return await servicio.crear_servicio(
        uow,
        CreateServicio(
            nro_servicio=nro,
            codigo_radio="R1",
            fecha=date(2026, 1, 15),
            dominio="ABC123",
            cod_productor=7,
            periodo_id=periodo_id,
            tipo_servicio_id=tipo_servicio_id,
        ),
        rol=RolUsuario.ADMIN,
    )


async def _armar_periodo_completo(uow, anio, mes, nombre):
    """Period with 3 tipos, capitas 10/5/2, servicios 4/10/4, alicuotas 120/130/150."""
    p = await _crear_periodo(uow, anio, mes, nombre)
    ts_bas = await _crear_ts(uow, "Automotores", "Básico", "basico")
    ts_com = await _crear_ts(uow, "Automotores", "Completo", "completo")
    ts_vip = await _crear_ts(uow, "Automotores", "VIP", "vip")
    await _crear_capita(uow, p.id, ts_bas.id, 10)
    await _crear_capita(uow, p.id, ts_com.id, 5)
    await _crear_capita(uow, p.id, ts_vip.id, 2)
    await _crear_alicuota(uow, p.id, ts_bas.id, 0.6, 120.0)
    await _crear_alicuota(uow, p.id, ts_com.id, 0.6, 130.0)
    await _crear_alicuota(uow, p.id, ts_vip.id, 0.6, 150.0)
    for i in range(4):
        await _crear_servicio(uow, f"{nombre}-B{i}", p.id, ts_bas.id)
    for i in range(10):
        await _crear_servicio(uow, f"{nombre}-C{i}", p.id, ts_com.id)
    for i in range(4):
        await _crear_servicio(uow, f"{nombre}-V{i}", p.id, ts_vip.id)
    return p


def test_previsualizar_full_cuadro():
    async def main():
        async with PostgresUoW() as uow:
            p = await _armar_periodo_completo(uow, 2026, 1, "Ene")
            cuadro = await cierre.previsualizar_cierre(uow, p.id, Decimal("0"))
            assert cuadro["nombre"] == "Ene"
            assert cuadro["aumento"] == "0.00"
            assert cuadro["capitas"] == {
                "total": 17,
                "basico": 10,
                "completo": 5,
                "vip": 2,
                "rama_87": 0,
                "rama_89": 0,
                "rama_90": 0,
            }
            assert cuadro["servicios"] == {
                "total": 18,
                "basico": 4,
                "completo": 10,
                "vip": 4,
            }
            assert cuadro["coef_uso"] == "1.0588"
            assert cuadro["coef_indice"] == "0.6"
            assert cuadro["valores"] == {
                "basico": "120.00",
                "completo": "130.00",
                "vip": "150.00",
            }
            assert cuadro["total_a_pagar"] == "2150.00"

    run_test(main)


def test_previsualizar_no_writes():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "Automotores", "Básico", "basico")
            await _crear_alicuota(uow, prev.id, ts.id, 0.5, 100.0)
            await _crear_alicuota(uow, target.id, ts.id, 0.5, 999.0)
            await _crear_capita(uow, target.id, ts.id, 10)
            cuadro = await cierre.previsualizar_cierre(uow, target.id, Decimal("10"))
            # el override en memoria usa el set recalculado (110.00)...
            assert cuadro["valores"]["basico"] == "110.00"
            # ...pero nada se persiste: sin cierre y alícuotas intactas
            assert await uow.cierres.get_oficial(target.id) is None
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            assert [a.valor for a in actuales] == [999.0]

    run_test(main)


def test_previsualizar_aumento_parity():
    async def main():
        async with PostgresUoW() as uow:
            prev = await _crear_periodo(uow, 2026, 1, "Ene")
            target = await _crear_periodo(uow, 2026, 2, "Feb")
            ts_bas = await _crear_ts(uow, "Automotores", "Básico", "basico")
            ts_com = await _crear_ts(uow, "Automotores", "Completo", "completo")
            ts_vip = await _crear_ts(uow, "Automotores", "VIP", "vip")
            await _crear_alicuota(uow, prev.id, ts_bas.id, 0.5, 100.0)
            await _crear_alicuota(uow, prev.id, ts_com.id, 0.5, 200.0)
            await _crear_alicuota(uow, prev.id, ts_vip.id, 0.5, 300.0)
            await _crear_capita(uow, target.id, ts_bas.id, 10)
            await _crear_capita(uow, target.id, ts_com.id, 5)
            await _crear_capita(uow, target.id, ts_vip.id, 2)
            preview = await cierre.previsualizar_cierre(uow, target.id, Decimal("10"))
            # alícuotas = valor * (1 + aumento/100) del set anterior
            assert preview["valores"] == {
                "basico": "110.00",
                "completo": "220.00",
                "vip": "330.00",
            }
            # el snapshot del cierre real coincide con la previsualización
            c = await cierre.cerrar_periodo(uow, target.id, Decimal("10"))
            assert c.snapshot == preview

    run_test(main)


def test_previsualizar_cap_total_zero():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts = await _crear_ts(uow, "Automotores", "Básico", "basico")
            await _crear_alicuota(uow, p.id, ts.id, 0.5, 100.0)
            await _crear_servicio(uow, "Ene-S1", p.id, ts.id)
            cuadro = await cierre.previsualizar_cierre(uow, p.id, Decimal("0"))
            assert cuadro["capitas"]["total"] == 0
            assert cuadro["coef_uso"] == "0"
            assert cuadro["total_a_pagar"] == "0.00"

    run_test(main)


def test_previsualizar_missing_alicuota_valor_zero():
    async def main():
        async with PostgresUoW() as uow:
            p = await _crear_periodo(uow, 2026, 1, "Ene")
            ts_bas = await _crear_ts(uow, "Automotores", "Básico", "basico")
            ts_vip = await _crear_ts(uow, "Automotores", "VIP", "vip")
            await _crear_capita(uow, p.id, ts_bas.id, 10)
            await _crear_capita(uow, p.id, ts_vip.id, 2)
            await _crear_alicuota(uow, p.id, ts_bas.id, 0.5, 100.0)
            cuadro = await cierre.previsualizar_cierre(uow, p.id, Decimal("0"))
            assert cuadro["valores"]["vip"] == "0.00"

    run_test(main)
