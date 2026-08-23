"""Use cases for Cierre de Periodo.

``recalcular_aumento`` is a pure function (no I/O) so it can be unit-tested
without a database. Rounding uses Decimal ROUND_HALF_UP to two decimals; a
resulting valor <= 0 raises before any write happens.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from src.domain.dto.create import CreateCierre
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import (
    PeriodoAlreadyClosedError,
    PeriodoNotClosedError,
    RecalculoInvalidoError,
)
from src.domain.models.entities import Alicuota, Cierre, Periodo
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


def _mismo_conjunto(a: list[Alicuota], b: list[Alicuota]) -> bool:
    """True when both lists describe the same alicuota set (order-insensitive).

    Each alicuota is reduced to ``(tipo_servicio_id, coeficiente, valor)`` with the
    valor normalized through ``Decimal(str(...))`` so float representation noise does
    not produce a spurious "changed" result.
    """

    def _firma(items: list[Alicuota]) -> set[tuple[int, float, Decimal]]:
        return {(x.tipo_servicio_id, x.coeficiente, Decimal(str(x.valor))) for x in items}

    return _firma(a) == _firma(b)


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
    with no earlier period keeps its manually entered alicuotas untouched. If the new
    set differs and later periods already hold official cierres, they are re-closed in
    the same transaction (cascade).
    """
    dto = CreateCierre(aumento=Decimal(str(aumento)), motivo=motivo)
    target = await uow.periodos.get(periodo_id)
    if await uow.cierres.get_oficial(periodo_id) is not None:
        raise PeriodoAlreadyClosedError(periodo_id)

    creado, _ = await _cerrar_y_cascada(uow, target, dto, demote=False)
    await uow.commit()
    return creado


async def generar_nuevo_cierre(
    uow: UnitOfWorkPort,
    periodo_id: int,
    aumento: Decimal | float,
    motivo: str | None = None,
) -> Cierre:
    """Re-close an already-official period with a new ``aumento``.

    Raises ``PeriodoNotClosedError`` when the period has no ``oficial`` cierre.
    Demotes the prior official cierre, inserts a new one (``origen=manual``), and
    cascades the recalculation to later official periods — all in ONE atomic commit.
    """
    dto = CreateCierre(aumento=Decimal(str(aumento)), motivo=motivo)
    target = await uow.periodos.get(periodo_id)
    if await uow.cierres.get_oficial(periodo_id) is None:
        raise PeriodoNotClosedError(periodo_id)

    creado, _ = await _cerrar_y_cascada(uow, target, dto, demote=True)
    await uow.commit()
    return creado


async def _cerrar_y_cascada(
    uow: UnitOfWorkPort,
    target: Periodo,
    dto: CreateCierre,
    *,
    demote: bool,
) -> tuple[Cierre, bool]:
    """Recalculate, (optionally) demote, and insert the cierre for ``target``.

    Returns ``(cierre, changed)`` where ``changed`` is True only when the recalculated
    alicuota set differs from the current one and was replaced. Never commits: the
    caller owns the single atomic ``commit()``.
    """
    prev = await uow.periodos.get_previous(target.anio, target.mes)
    changed = False
    if prev is not None:
        prev_alicuotas = await uow.alicuotas.get_by_keys(periodo_id=prev.id)
        recalculadas = recalcular_aumento(prev_alicuotas, dto.aumento)
        nuevas = [a.model_copy(update={"periodo_id": target.id}) for a in recalculadas]
        actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
        changed = not _mismo_conjunto(nuevas, actuales)
        if changed:
            await uow.alicuotas.reemplazar_por_periodo(target.id, nuevas)

    if demote:
        await uow.cierres.demote_oficial(target.id)

    version = await uow.cierres.next_version(target.id)
    cierre = Cierre(
        periodo_id=target.id,
        version=version,
        estado=EstadoCierre.OFICIAL,
        origen=OrigenCierre.MANUAL,
        motivo=dto.motivo,
        aumento=dto.aumento,
    )
    creado = await uow.cierres.add(cierre)

    if changed:
        await _aplicar_cascada(uow, target, dto.motivo)
    return creado, changed


async def _aplicar_cascada(
    uow: UnitOfWorkPort, origen: Periodo, motivo_base: str | None
) -> None:
    """Re-close every later official period M in ascending ``(anio, mes)`` order.

    Each M is recalculated from its immediate previous period's NEW alicuotas by M's
    own ``aumento``, then demoted and re-inserted as ``origen=cascada``. Stops at the
    first later period without an official cierre. ``motivo_base`` is the reason on the
    origin cierre; cascaded cierres name the origin period instead.
    """
    for m in await uow.periodos.get_following(origen.anio, origen.mes):
        oficial_m = await uow.cierres.get_oficial(m.id)
        if oficial_m is None:
            break
        prev_m = await uow.periodos.get_previous(m.anio, m.mes)
        if prev_m is None:
            break
        prev_alicuotas = await uow.alicuotas.get_by_keys(periodo_id=prev_m.id)
        recalculadas = recalcular_aumento(prev_alicuotas, oficial_m.aumento)
        nuevas = [a.model_copy(update={"periodo_id": m.id}) for a in recalculadas]
        await uow.alicuotas.reemplazar_por_periodo(m.id, nuevas)
        await uow.cierres.demote_oficial(m.id)
        version = await uow.cierres.next_version(m.id)
        await uow.cierres.add(
            Cierre(
                periodo_id=m.id,
                version=version,
                estado=EstadoCierre.OFICIAL,
                origen=OrigenCierre.CASCADA,
                motivo=f"cascada por {origen.nombre}",
                aumento=oficial_m.aumento,
            )
        )
