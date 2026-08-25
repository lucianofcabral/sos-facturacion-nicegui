"""Unit tests for the pure ``cuadro_de_snapshot`` helper (no DB).

``cuadro_de_snapshot`` unwraps both snapshot formats — the legacy
``{"sintesis": {...}}`` wrapper and the new direct-cuadro format — returning the
full síntesis cuadro dict (or None when absent/unrecognizable).
"""

from __future__ import annotations

from src.application.use_cases.cierre import cuadro_de_snapshot, total_de_snapshot


def test_cuadro_de_snapshot_legacy_sintesis():
    assert cuadro_de_snapshot({"sintesis": {"total_a_pagar": "1234.56"}}) == {
        "total_a_pagar": "1234.56"
    }


def test_cuadro_de_snapshot_direct_cuadro():
    snapshot = {
        "nombre": "Ene",
        "capitas": {"total": 17},
        "total_a_pagar": "2150.00",
    }
    assert cuadro_de_snapshot(snapshot) is snapshot


def test_cuadro_de_snapshot_none():
    assert cuadro_de_snapshot(None) is None


def test_cuadro_de_snapshot_unrecognizable():
    assert cuadro_de_snapshot({"total_a_pagar": "100.00"}) is None
    assert cuadro_de_snapshot({"nombre": "Ene"}) is None


def test_cuadro_de_snapshot_prefers_legacy_wrapper():
    snapshot = {
        "sintesis": {"capitas": {"total": 1}},
        "capitas": {"total": 2},
    }
    assert cuadro_de_snapshot(snapshot) == {"capitas": {"total": 1}}


def test_total_de_snapshot_uses_cuadro_helper():
    # Regresión: total_de_snapshot debe seguir leyendo ambos formatos tras
    # delegar en cuadro_de_snapshot.
    assert total_de_snapshot({"sintesis": {"total_a_pagar": "10.00"}}) is not None
    assert (
        total_de_snapshot({"capitas": {"total": 1}, "total_a_pagar": "20.00"})
        is not None
    )
