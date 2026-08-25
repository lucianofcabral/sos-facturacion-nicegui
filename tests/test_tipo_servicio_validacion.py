"""Unit tests for the pure ``validar_tipo_servicio`` form validator (no DB).

Mirrors the ``TipoServicio`` entity constraints (required fields and max
lengths) to make sure the dialog's inline hints stay in sync with the domain.
"""

from __future__ import annotations

from src.ui.dialogos.tipo_servicio import validar_tipo_servicio


def _valores(**overrides) -> dict:
    base = {
        "rama": "Automotores",
        "nombre": "Básico",
        "codigo": "659",
        "categoria": "basico",
    }
    base.update(overrides)
    return base


def test_valores_completos_son_validos():
    assert validar_tipo_servicio(_valores()) is None


def test_campo_obligatorio_faltante_advertencia():
    for campo in ("rama", "nombre", "codigo", "categoria"):
        falta = None if campo == "categoria" else ""
        assert validar_tipo_servicio(_valores(**{campo: falta})) is not None


def test_espacios_en_blanco_cuentan_como_vacio():
    assert validar_tipo_servicio(_valores(nombre="   ")) is not None


def test_longitudes_maximas():
    assert "rama" in validar_tipo_servicio(_valores(rama="X" * 26))
    assert "nombre" in validar_tipo_servicio(_valores(nombre="X" * 51))
    assert "código" in validar_tipo_servicio(_valores(codigo="X" * 11))


def test_limite_exacto_es_valido():
    assert validar_tipo_servicio(_valores(rama="X" * 25)) is None
    assert validar_tipo_servicio(_valores(nombre="X" * 50)) is None
    assert validar_tipo_servicio(_valores(codigo="X" * 10)) is None
