"""Integration tests for snapshot persistence and síntesis (testcontainers).

Covers the repository layer (``get_oficiales_recientes``, Jsonb ``add``
override) and the closure use cases (snapshot population in both paths,
``armar_hoja_sintesis``).
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
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.models.entities import Cierre
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


_SHEET_KEYS = {
    "servicios_total",
    "servicios_basico",
    "servicios_completo",
    "servicios_vip",
    "sintesis",
}


async def _armar_periodo_completo(uow, anio, mes, nombre, *, con_servicios=True):
    """Create a period with tipos/capitas/servicios/alicuotas and return it."""
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
    if con_servicios:
        for i in range(4):
            await _crear_servicio(uow, f"{nombre}-B{i}", p.id, ts_bas.id)
        for i in range(10):
            await _crear_servicio(uow, f"{nombre}-C{i}", p.id, ts_com.id)
        for i in range(4):
            await _crear_servicio(uow, f"{nombre}-V{i}", p.id, ts_vip.id)
    return p


# --- Use case: snapshot population --------------------------------------------


def test_cerrar_periodo_puebla_snapshot():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _armar_periodo_completo(uow, 2026, 1, "Ene")
            c = await cierre.cerrar_periodo(uow, ene.id, Decimal("0"))
            assert c.snapshot is not None
            assert set(c.snapshot.keys()) == _SHEET_KEYS
            sintesis = c.snapshot["sintesis"]
            assert sintesis["capitas"]["total"] == 17
            assert sintesis["servicios"]["total"] == 18
            assert sintesis["total_a_pagar"] == "2150.00"
            assert len(c.snapshot["servicios_basico"]) == 4
            assert len(c.snapshot["servicios_completo"]) == 10
            assert len(c.snapshot["servicios_vip"]) == 4

    run_test(main)


def test_generar_nuevo_cierre_puebla_snapshot_demoted_keeps_own():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _armar_periodo_completo(uow, 2026, 1, "Ene")
            await cierre.cerrar_periodo(uow, ene.id, Decimal("0"))
            viejo = await uow.cierres.get_oficial(ene.id)
            nuevo = await cierre.generar_nuevo_cierre(uow, ene.id, Decimal("10"))
            assert nuevo.snapshot is not None
            assert set(nuevo.snapshot.keys()) == _SHEET_KEYS
            demoted = await uow.cierres.get(viejo.id)
            assert demoted.estado == EstadoCierre.NO_OFICIAL
            assert demoted.snapshot is not None  # conserva el suyo

    run_test(main)


def test_cascade_cierres_snapshotted():
    async def main():
        async with PostgresUoW() as uow:
            dic = await _crear_periodo(uow, 2025, 12, "Dic")
            ene = await _crear_periodo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            ts = await _crear_ts(uow, "Automotores", "Básico", "basico")
            await _crear_alicuota(uow, dic.id, ts.id, 0.5, 100.0)
            await cierre.cerrar_periodo(uow, dic.id, Decimal("0"))
            await cierre.cerrar_periodo(uow, ene.id, Decimal("10"))
            await cierre.cerrar_periodo(uow, feb.id, Decimal("10"))
            await cierre.generar_nuevo_cierre(uow, ene.id, Decimal("20"))
            for pid in (ene.id, feb.id):
                oficial = await uow.cierres.get_oficial(pid)
                assert oficial.snapshot is not None
                assert set(oficial.snapshot.keys()) == _SHEET_KEYS
            feb_of = await uow.cierres.get_oficial(feb.id)
            assert feb_of.origen == OrigenCierre.CASCADA

    run_test(main)


def test_sin_servicios_hojas_vacias_counts_cero():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _armar_periodo_completo(uow, 2026, 1, "Ene", con_servicios=False)
            c = await cierre.cerrar_periodo(uow, ene.id, Decimal("0"))
            assert c.snapshot is not None
            assert c.snapshot["servicios_total"] == []
            assert c.snapshot["servicios_basico"] == []
            assert c.snapshot["servicios_completo"] == []
            assert c.snapshot["servicios_vip"] == []
            assert c.snapshot["sintesis"]["servicios"]["total"] == 0
            assert c.snapshot["sintesis"]["capitas"]["total"] == 17

    run_test(main)


# --- Use case: armar_hoja_sintesis --------------------------------------------


async def _add_oficial_marker(uow, periodo_id, version, marker):
    snapshot = {"sintesis": {"nombre": marker}, "servicios_total": []}
    return await uow.cierres.add(
        _cierre(
            periodo_id,
            version,
            EstadoCierre.OFICIAL,
            OrigenCierre.MANUAL,
            snapshot=snapshot,
        )
    )


def test_armar_hoja_sintesis_actual_mas_12_previos():
    async def main():
        async with PostgresUoW() as uow:
            # 15 previos (2025-01 .. 2026-03) + target (2026-04)
            for i, (anio, mes) in enumerate(
                [(2025, m) for m in range(1, 13)] + [(2026, m) for m in (1, 2, 3)],
                start=1,
            ):
                p = await _crear_periodo(uow, anio, mes, f"P{i}")
                await _add_oficial_marker(uow, p.id, 1, f"P{i}")
            target = await _crear_periodo(uow, 2026, 4, "target")
            await _add_oficial_marker(uow, target.id, 1, "actual")
            hoja = await cierre.armar_hoja_sintesis(uow, 2026, 4)
            assert hoja["actual"]["nombre"] == "actual"
            assert len(hoja["previos"]) == 12
            assert hoja["previos"][0]["nombre"] == "P15"
            assert hoja["previos"][-1]["nombre"] == "P4"

    run_test(main)


def test_armar_hoja_sintesis_fewer_than_12():
    async def main():
        async with PostgresUoW() as uow:
            for i in range(1, 4):
                p = await _crear_periodo(uow, 2026, i, f"P{i}")
                await _add_oficial_marker(uow, p.id, 1, f"P{i}")
            target = await _crear_periodo(uow, 2026, 4, "target")
            await _add_oficial_marker(uow, target.id, 1, "actual")
            hoja = await cierre.armar_hoja_sintesis(uow, 2026, 4)
            assert hoja["actual"]["nombre"] == "actual"
            assert [c["nombre"] for c in hoja["previos"]] == ["P3", "P2", "P1"]

    run_test(main)


def test_armar_hoja_sintesis_null_snapshot_recompute():
    async def main():
        async with PostgresUoW() as uow:
            ene = await _armar_periodo_completo(uow, 2026, 1, "Ene")
            feb = await _crear_periodo(uow, 2026, 2, "Feb")
            # cierre previo SIN snapshot (slice previo) → recompute on-demand
            await uow.cierres.add(
                _cierre(ene.id, 1, EstadoCierre.OFICIAL, OrigenCierre.MANUAL)
            )
            await _add_oficial_marker(uow, feb.id, 1, "actual")
            hoja = await cierre.armar_hoja_sintesis(uow, 2026, 2)
            assert hoja["actual"]["nombre"] == "actual"
            assert len(hoja["previos"]) == 1
            previo = hoja["previos"][0]
            assert previo["capitas"]["total"] == 17
            assert previo["total_a_pagar"] == "2150.00"

    run_test(main)
