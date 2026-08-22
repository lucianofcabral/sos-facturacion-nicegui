"""Use cases for Cierre de Periodo.

``recalcular_aumento`` is a pure function (no I/O) so it can be unit-tested
without a database. Rounding uses Decimal ROUND_HALF_UP to two decimals; a
resulting valor <= 0 raises before any write happens.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.domain.exceptions import RecalculoInvalidoError
from src.domain.models.entities import Alicuota


def recalcular_aumento(
    prev_alicuotas: list[Alicuota], aumento: Decimal
) -> list[Alicuota]:
    """Recalculate each alicuota as ``valor * (1 + aumento/100)`` (2dp half-up).

    Keeps the source ``periodo_id``; the caller remaps it to the target period
    with ``model_copy``. Raises ``RecalculoInvalidoError`` if any result is
    <= 0 after rounding, before returning.
    """
    factor = Decimal(1) + aumento / Decimal(100)
    resultado: list[Alicuota] = []
    for a in prev_alicuotas:
        redondeado = (Decimal(str(a.valor)) * factor).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if redondeado <= 0:
            raise RecalculoInvalidoError(a.tipo_servicio_id)
        resultado.append(a.model_copy(update={"valor": float(redondeado)}))
    return resultado
