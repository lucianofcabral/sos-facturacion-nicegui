"""Use cases for Cierre de Periodo.

``recalcular_aumento`` is a pure function (no I/O) so it can be unit-tested
without a database. Rounding uses Decimal ROUND_HALF_UP to two decimals; a
resulting valor <= 0 raises before any write happens.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.domain.dto.create import CreateCierre
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import PeriodoAlreadyClosedError, RecalculoInvalidoError
from src.domain.models.entities import Alicuota, Cierre
from src.domain.ports.uow import UnitOfWorkPort


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


async def cerrar_periodo(
    uow: UnitOfWorkPort,
    periodo_id: int,
    aumento: Decimal | float,
    motivo: str | None = None,
) -> Cierre:
    """Create the first official cierre for a period and apply recalculated alicuotas.

    In ONE atomic commit: resolve the previous period (max ``(anio, mes)`` strictly
    less than the target), recalculate its alicuotas by ``(1 + aumento/100)``, replace
    the target's alicuota set, then insert the ``oficial``/``manual`` cierre. A period
    with no earlier period keeps its manually entered alicuotas untouched.
    """
    dto = CreateCierre(aumento=Decimal(str(aumento)), motivo=motivo)
    target = await uow.periodos.get(periodo_id)
    if await uow.cierres.get_oficial(periodo_id) is not None:
        raise PeriodoAlreadyClosedError(periodo_id)

    prev = await uow.periodos.get_previous(target.anio, target.mes)
    if prev is not None:
        prev_alicuotas = await uow.alicuotas.get_by_keys(periodo_id=prev.id)
        recalculadas = recalcular_aumento(prev_alicuotas, dto.aumento)
        nuevas = [a.model_copy(update={"periodo_id": periodo_id}) for a in recalculadas]
        await uow.alicuotas.reemplazar_por_periodo(periodo_id, nuevas)

    version = await uow.cierres.next_version(periodo_id)
    cierre = Cierre(
        periodo_id=periodo_id,
        version=version,
        estado=EstadoCierre.OFICIAL,
        origen=OrigenCierre.MANUAL,
        motivo=dto.motivo,
        aumento=dto.aumento,
    )
    creado = await uow.cierres.add(cierre)
    await uow.commit()
    return creado
