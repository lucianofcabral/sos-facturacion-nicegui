"""Unit tests for the pure ``recalcular_aumento`` function (no DB).

These pin the rounding (ROUND_HALF_UP to 2 decimals), factor math, rebaja
handling, zero-result rejection, and metadata preservation, plus the
``CreateCierre`` input validation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.application.use_cases.cierre import _mismo_conjunto, recalcular_aumento
from src.domain.dto.create import CreateCierre
from src.domain.exceptions import RecalculoInvalidoError
from src.domain.models.entities import Alicuota


def _alicuota(
    periodo_id: int, tipo_servicio_id: int, coeficiente: float, valor: float
) -> Alicuota:
    return Alicuota(
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_servicio_id,
        coeficiente=coeficiente,
        valor=valor,
    )


def test_rounding_half_up():
    prev = [_alicuota(1, 10, 0.5, 10.005)]
    result = recalcular_aumento(prev, Decimal("0"))
    assert result[0].valor == 10.01


def test_rebaja_10_percent():
    prev = [_alicuota(1, 10, 0.5, 100.0)]
    result = recalcular_aumento(prev, Decimal("-10"))
    assert result[0].valor == 90.00


def test_factor_math():
    prev = [_alicuota(1, 10, 0.5, 100.0)]
    result = recalcular_aumento(prev, Decimal("10"))
    assert result[0].valor == 110.00


def test_reject_zeroed_valor():
    prev = [_alicuota(1, 10, 0.5, 0.01)]
    with pytest.raises(RecalculoInvalidoError):
        recalcular_aumento(prev, Decimal("-100"))


def test_reject_post_rounding_zero():
    prev = [_alicuota(1, 10, 0.5, 0.01)]
    with pytest.raises(RecalculoInvalidoError):
        recalcular_aumento(prev, Decimal("-99"))


def test_tiny_valor_survives_rounding():
    prev = [_alicuota(1, 10, 0.5, 0.005)]
    result = recalcular_aumento(prev, Decimal("0"))
    assert result[0].valor == 0.01


def test_preserves_metadata():
    prev = [_alicuota(1, 42, 0.35, 200.0)]
    result = recalcular_aumento(prev, Decimal("5"))
    assert result[0].periodo_id == 1
    assert result[0].tipo_servicio_id == 42
    assert result[0].coeficiente == 0.35


def test_create_cierre_rejects_at_or_below_minus_100():
    with pytest.raises(ValidationError):
        CreateCierre(aumento=Decimal("-100"))
    with pytest.raises(ValidationError):
        CreateCierre(aumento=Decimal("-100.01"))


def test_create_cierre_accepts_above_minus_100():
    cierre = CreateCierre(aumento=Decimal("-99.99"), motivo="rebaja")
    assert cierre.aumento == Decimal("-99.99")
    assert cierre.motivo == "rebaja"


def test_mismo_conjunto_order_insensitive():
    a = [_alicuota(1, 10, 0.5, 100.0), _alicuota(1, 20, 0.5, 200.0)]
    b = [_alicuota(1, 20, 0.5, 200.0), _alicuota(1, 10, 0.5, 100.0)]
    assert _mismo_conjunto(a, b) is True


def test_mismo_conjunto_valor_diff():
    a = [_alicuota(1, 10, 0.5, 100.0)]
    b = [_alicuota(1, 10, 0.5, 110.0)]
    assert _mismo_conjunto(a, b) is False


def test_mismo_conjunto_coeficiente_diff():
    a = [_alicuota(1, 10, 0.5, 100.0)]
    b = [_alicuota(1, 10, 0.6, 100.0)]
    assert _mismo_conjunto(a, b) is False


def test_mismo_conjunto_tipo_diff():
    a = [_alicuota(1, 10, 0.5, 100.0)]
    b = [_alicuota(1, 20, 0.5, 100.0)]
    assert _mismo_conjunto(a, b) is False


def test_mismo_conjunto_extra_element():
    a = [_alicuota(1, 10, 0.5, 100.0), _alicuota(1, 20, 0.5, 200.0)]
    b = [_alicuota(1, 10, 0.5, 100.0)]
    assert _mismo_conjunto(a, b) is False


def test_mismo_conjunto_empty_equal():
    assert _mismo_conjunto([], []) is True
