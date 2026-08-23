"""Unit tests for the pure síntesis snapshot functions (no DB).

Pins the div-zero guard, bracket lookup, per-tipo/global coefficients, value
selection at the chosen coefficient, total half-up rounding, category-based
classification (basico/completo/vip/rama_87/89/90, independent of the display
name), and the JSON-native snapshot builder.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from src.application.use_cases.cierre import _construir_snapshot, computar_sintesis
from src.domain.models.entities import (
    Alicuota,
    CapitaPeriodo,
    Periodo,
    Servicio,
    SintesisPeriodo,
    TipoServicio,
)


def _tipo(
    id: int, categoria: str, nombre: str | None = None, rama: str = "Automotores"
) -> TipoServicio:
    if nombre is None:
        nombre = {
            "basico": "Básico",
            "completo": "Completo",
            "vip": "VIP",
            "rama_87": "Rama 87",
            "rama_89": "Rama 89",
            "rama_90": "Rama 90",
        }[categoria]
    return TipoServicio(
        id=id, rama=rama, nombre=nombre, codigo=str(id), categoria=categoria
    )


def _capita(tipo_id: int, capitas: int) -> CapitaPeriodo:
    return CapitaPeriodo(periodo_id=1, tipo_servicio_id=tipo_id, capitas=capitas)


def _alicuota(tipo_id: int, coeficiente: float, valor: float) -> Alicuota:
    return Alicuota(
        periodo_id=1, tipo_servicio_id=tipo_id, coeficiente=coeficiente, valor=valor
    )


_PERIODO = Periodo(id=1, nombre="Enero 2026", anio=2026, mes=1)


def _run(
    capitas: list[CapitaPeriodo],
    alicuotas: list[Alicuota],
    servicio_conteos: dict[int, int],
    tipos: dict[int, TipoServicio],
    aumento: str = "10",
) -> SintesisPeriodo:
    return computar_sintesis(
        capitas, alicuotas, servicio_conteos, tipos, _PERIODO, Decimal(aumento)
    )


# --- capitas, service counts, coef uso (spec scenario) -------------------------


def test_computar_sintesis_counts_and_per_tipo_coef():
    tipos = {1: _tipo(1, "basico"), 2: _tipo(2, "completo"), 3: _tipo(3, "vip")}
    capitas = [_capita(1, 10), _capita(2, 5), _capita(3, 2)]
    s = _run(capitas, [], {1: 4, 2: 10, 3: 4}, tipos)
    assert s.capitas_total == 17
    assert s.capitas_basico == 10
    assert s.capitas_completo == 5
    assert s.capitas_vip == 2
    assert s.servicios_total == 18
    assert s.servicios_basico == 4
    assert s.servicios_completo == 10
    assert s.servicios_vip == 4
    assert s.coef_uso_basico == Decimal("0.4")
    assert s.coef_uso_completo == Decimal("2.0")
    assert s.coef_uso_vip == Decimal("2.0")
    assert s.coef_uso == Decimal("1.0588")  # global = 18/17 quantized 4dp
    assert s.name == "Enero 2026"
    assert s.aumento == Decimal("10")


# --- division by zero ----------------------------------------------------------


def test_computar_sintesis_div_zero_per_tipo():
    tipos = {1: _tipo(1, "basico"), 2: _tipo(2, "completo")}
    capitas = [_capita(1, 0), _capita(2, 5)]
    s = _run(capitas, [], {1: 4, 2: 10}, tipos)
    assert s.coef_uso_basico == Decimal("0")
    assert s.coef_uso_completo == Decimal("2.0")


def test_computar_sintesis_div_zero_global():
    tipos = {1: _tipo(1, "basico")}
    s = _run([_capita(1, 0)], [], {1: 0}, tipos)
    assert s.coef_uso == Decimal("0")
    assert s.capitas_total == 0


# --- bracket lookup ------------------------------------------------------------


def test_computar_sintesis_bracket_lowest_ge():
    tipos = {1: _tipo(1, "basico")}
    alicuotas = [_alicuota(1, 0.5, 100.0), _alicuota(1, 0.6, 120.0), _alicuota(1, 0.7, 140.0)]
    s = _run([_capita(1, 100)], alicuotas, {1: 55}, tipos)  # coef_uso = 0.55
    assert s.coef_indice == Decimal("0.6")
    assert s.valor_basico == Decimal("120.00")
    assert s.total == Decimal("12000.00")


def test_computar_sintesis_bracket_fallback_max():
    tipos = {1: _tipo(1, "basico")}
    alicuotas = [_alicuota(1, 0.5, 100.0), _alicuota(1, 0.6, 120.0)]
    s = _run([_capita(1, 10)], alicuotas, {1: 10}, tipos)  # coef_uso = 1.0 > all
    assert s.coef_indice == Decimal("0.6")


def test_computar_sintesis_sin_alicuotas_coef_indice_zero():
    tipos = {1: _tipo(1, "basico")}
    s = _run([_capita(1, 10)], [], {1: 4}, tipos)
    assert s.coef_indice == Decimal("0")
    assert s.valor_basico == Decimal("0.00")
    assert s.total == Decimal("0.00")


# --- valores and total ---------------------------------------------------------


def test_computar_sintesis_valores_and_total():
    tipos = {1: _tipo(1, "basico")}
    alicuotas = [_alicuota(1, 0.5, 100.0), _alicuota(1, 0.6, 120.0), _alicuota(1, 0.7, 140.0)]
    s = _run([_capita(1, 10)], alicuotas, {1: 6}, tipos)  # coef_uso = 0.6
    assert s.coef_indice == Decimal("0.6")
    assert s.valor_basico == Decimal("120.00")
    assert s.total == Decimal("1200.00")


def test_computar_sintesis_total_sums_automotores():
    tipos = {1: _tipo(1, "basico"), 2: _tipo(2, "completo"), 3: _tipo(3, "vip")}
    alicuotas = [
        _alicuota(1, 0.6, 120.0),
        _alicuota(2, 0.6, 130.0),
        _alicuota(3, 0.6, 150.0),
    ]
    capitas = [_capita(1, 10), _capita(2, 5), _capita(3, 2)]
    s = _run(capitas, alicuotas, {1: 4, 2: 10, 3: 4}, tipos)
    assert s.total == Decimal("2150.00")


def test_computar_sintesis_tipo_faltante_valor_zero():
    tipos = {1: _tipo(1, "basico"), 2: _tipo(2, "completo"), 3: _tipo(3, "vip")}
    alicuotas = [_alicuota(1, 0.6, 120.0), _alicuota(2, 0.6, 130.0)]  # sin VIP
    capitas = [_capita(1, 10), _capita(2, 5), _capita(3, 2)]
    s = _run(capitas, alicuotas, {1: 4, 2: 10, 3: 4}, tipos)
    assert s.valor_vip == Decimal("0.00")
    assert s.total == Decimal("1850.00")


# --- Decimal safety ------------------------------------------------------------


def test_computar_sintesis_decimal_half_up():
    tipos = {1: _tipo(1, "basico")}
    alicuotas = [_alicuota(1, 0.5, 10.005)]
    s = _run([_capita(1, 2)], alicuotas, {1: 1}, tipos)  # coef_uso = 0.5
    assert s.valor_basico == Decimal("10.01")
    assert s.total == Decimal("20.02")


# --- classification (category-driven, name-independent) -----------------------


def test_computar_sintesis_clasificacion_por_categoria():
    tipos = {
        1: _tipo(1, "basico", nombre="Nombre Arbitrario 123"),  # el nombre no importa
        2: _tipo(2, "completo"),
        3: _tipo(3, "vip"),
        4: _tipo(4, "rama_87"),
        5: _tipo(5, "rama_89"),
        6: _tipo(6, "rama_90"),
    }
    capitas = [
        _capita(1, 10),
        _capita(2, 5),
        _capita(3, 2),
        _capita(4, 1),
        _capita(5, 2),
        _capita(6, 3),
    ]
    s = _run(capitas, [], {1: 4, 2: 10, 3: 4, 4: 0, 5: 0, 6: 0}, tipos)
    assert s.capitas_basico == 10  # "Nombre Arbitrario 123" con categoria basico
    assert s.capitas_completo == 5
    assert s.capitas_vip == 2
    assert s.capitas_rama_87 == 1
    assert s.capitas_rama_89 == 2
    assert s.capitas_rama_90 == 3
    assert s.capitas_total == 17
    assert s.servicios_total == 18


def test_renombrar_no_cambia_bucket():
    # Un tipo con categoria basico sigue en el bucket basico aunque su nombre
    # coincida con "completo": la categoria manda, no el nombre.
    tipos = {1: _tipo(1, "basico", nombre="Completo")}
    s = _run([_capita(1, 10)], [], {1: 5}, tipos)
    assert s.capitas_basico == 10
    assert s.capitas_completo == 0


def test_computar_sintesis_coef_excluye_ramas():
    tipos = {
        1: _tipo(1, "basico"),
        2: _tipo(2, "completo"),
        3: _tipo(3, "vip"),
        4: _tipo(4, "rama_87"),
        5: _tipo(5, "rama_89"),
        6: _tipo(6, "rama_90"),
    }
    capitas = [
        _capita(1, 10),
        _capita(2, 5),
        _capita(3, 5),
        _capita(4, 50),
        _capita(5, 30),
        _capita(6, 20),
    ]
    # automotores s=10 / c=20; ramas s=100 / c=100 → coef_uso = 10/20
    s = _run(capitas, [], {1: 4, 2: 4, 3: 2, 4: 50, 5: 30, 6: 20}, tipos)
    assert s.capitas_total == 20
    assert s.servicios_total == 10
    assert s.coef_uso == Decimal("0.5000")
    assert s.capitas_rama_87 == 50
    assert s.capitas_rama_89 == 30
    assert s.capitas_rama_90 == 20


# --- _construir_snapshot -------------------------------------------------------


def test_construir_snapshot_5_keys_full_rows():
    tipos = {1: _tipo(1, "basico"), 2: _tipo(2, "completo")}
    servicios = [
        Servicio(
            nro_servicio="S001",
            codigo_radio="R1",
            fecha=date(2026, 1, 15),
            dominio="ABC123",
            cod_productor=7,
            periodo_id=1,
            tipo_servicio_id=1,
        ),
        Servicio(
            nro_servicio="S002",
            codigo_radio="R2",
            fecha=date(2026, 1, 16),
            dominio="XYZ789",
            cod_productor=8,
            periodo_id=1,
            tipo_servicio_id=2,
        ),
    ]
    cuadro = _run([_capita(1, 10), _capita(2, 5)], [], {1: 4, 2: 10}, tipos)
    snap = _construir_snapshot(servicios, tipos, cuadro)
    assert set(snap.keys()) == {
        "servicios_total",
        "servicios_basico",
        "servicios_completo",
        "servicios_vip",
        "sintesis",
    }
    assert snap["servicios_basico"] == [
        {
            "nro_servicio": "S001",
            "codigo_radio": "R1",
            "fecha": "2026-01-15",
            "dominio": "ABC123",
            "cod_productor": 7,
            "tipo": "Básico",
        }
    ]
    assert snap["servicios_completo"] == [
        {
            "nro_servicio": "S002",
            "codigo_radio": "R2",
            "fecha": "2026-01-16",
            "dominio": "XYZ789",
            "cod_productor": 8,
            "tipo": "Completo",
        }
    ]
    assert snap["servicios_vip"] == []
    assert len(snap["servicios_total"]) == 2
    # json.dumps must not raise on Decimal/date (all JSON-native)
    json.dumps(snap)


def test_construir_snapshot_empty_sheets():
    cuadro = _run([], [], {}, {})
    snap = _construir_snapshot([], {}, cuadro)
    assert snap["servicios_total"] == []
    assert snap["servicios_basico"] == []
    assert snap["servicios_completo"] == []
    assert snap["servicios_vip"] == []
    sintesis = snap["sintesis"]
    assert sintesis["capitas"]["total"] == 0
    assert sintesis["servicios"]["total"] == 0
    assert sintesis["total_a_pagar"] == "0.00"
    json.dumps(snap)


def test_construir_snapshot_sintesis_shape():
    cuadro = _run([_capita(1, 10), _capita(2, 5), _capita(3, 2)], [], {1: 4, 2: 10, 3: 4},
                  {1: _tipo(1, "basico"), 2: _tipo(2, "completo"), 3: _tipo(3, "vip")})
    snap = _construir_snapshot([], {}, cuadro)
    sintesis = snap["sintesis"]
    assert sintesis["nombre"] == "Enero 2026"
    assert sintesis["aumento"] == "10.00"
    assert sintesis["capitas"] == {
        "total": 17,
        "basico": 10,
        "completo": 5,
        "vip": 2,
        "rama_87": 0,
        "rama_89": 0,
        "rama_90": 0,
    }
    assert sintesis["servicios"] == {"total": 18, "basico": 4, "completo": 10, "vip": 4}
    assert sintesis["coef_uso"] == "1.06"
    assert sintesis["valores"] == {"basico": "0.00", "completo": "0.00", "vip": "0.00"}
    assert sintesis["total_a_pagar"] == "0.00"
