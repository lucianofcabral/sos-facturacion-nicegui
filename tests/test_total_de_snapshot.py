"""Unit tests for the pure ``total_de_snapshot`` helper (no DB).

``total_de_snapshot`` unwraps both snapshot formats — the legacy
``{"sintesis": {...}}`` wrapper and the new direct-cuadro format — returning the
official ``total_a_pagar`` as a Decimal (or None when absent).
"""

from __future__ import annotations

from decimal import Decimal

from src.application.use_cases.cierre import total_de_snapshot


def test_total_de_snapshot_legacy_sintesis():
    assert total_de_snapshot(
        {"sintesis": {"total_a_pagar": "1234.56"}}
    ) == Decimal("1234.56")


def test_total_de_snapshot_direct_cuadro():
    snapshot = {
        "nombre": "Ene",
        "capitas": {"total": 17},
        "total_a_pagar": "2150.00",
    }
    assert total_de_snapshot(snapshot) == Decimal("2150.00")


def test_total_de_snapshot_none_snapshot():
    assert total_de_snapshot(None) is None


def test_total_de_snapshot_missing_total():
    assert total_de_snapshot({"sintesis": {"nombre": "Ene"}}) is None
    assert total_de_snapshot({"capitas": {"total": 1}}) is None


def test_total_de_snapshot_prefers_legacy_wrapper():
    snapshot = {
        "sintesis": {"total_a_pagar": "100.00"},
        "total_a_pagar": "999.00",
    }
    assert total_de_snapshot(snapshot) == Decimal("100.00")
