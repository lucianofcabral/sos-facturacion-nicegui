"""Use cases for Cierre de Periodo.

``recalcular_aumento`` is a pure function (no I/O) so it can be unit-tested
without a database. Rounding uses Decimal ROUND_HALF_UP to two decimals; a
resulting valor <= 0 raises before any write happens.
"""

from __future__ import annotations

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal

from src.application.services.export_cierre import exportar_cierre
from src.domain.dto.create import CreateCierre
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import (
    PeriodoAlreadyClosedError,
    PeriodoNotClosedError,
    RecalculoInvalidoError,
)
from src.domain.models.entities import (
    Alicuota,
    CapitaPeriodo,
    Cierre,
    Periodo,
    SintesisPeriodo,
    TipoServicio,
)
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


def _clasificar_tipo(tipo: TipoServicio) -> str:
    """Return the tipo's calculation category (stable bucket key).

    The bucket comes from ``TipoServicio.categoria`` (controlled vocabulary),
    never from the ``nombre``: display names can change without affecting
    grouping, and multiple tipos may share a category (e.g. two "Básico" tipos
    with different radio codes).
    """
    return tipo.categoria.value


def _dec_str(value: Decimal) -> str:
    """Serialize a Decimal as a fixed 2dp string (ROUND_HALF_UP)."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def computar_sintesis(
    capitas: list[CapitaPeriodo],
    alicuotas: list[Alicuota],
    servicio_conteos: dict[int, int],
    tipos: dict[int, TipoServicio],
    periodo: Periodo,
    aumento: Decimal,
) -> SintesisPeriodo:
    """Pure equivalent of the legacy DataSintesis cuadro (no I/O).

    Buckets capitas and service counts by normalized tipo name; guards division
    by zero; computes the global coef de uso (4dp) that drives the bracket
    lookup; selects the lowest alicuota coefficient >= uso (fallback max, 0.0
    when there are no alicuotas); reads each tipo's valor at that coefficient
    (missing tipo -> 0.00); and totals ``Σ(valor x capitas)`` over the
    automotores buckets, rounded to 2dp half-up.
    """
    buckets: dict[str, list[int]] = {}
    for tipo in tipos.values():
        buckets.setdefault(_clasificar_tipo(tipo), []).append(tipo.id)

    cap_by_tipo = {c.tipo_servicio_id: c.capitas for c in capitas}

    def _sum_capitas(bucket: str) -> int:
        return sum(cap_by_tipo.get(tid, 0) for tid in buckets.get(bucket, []))

    def _sum_servicios(bucket: str) -> int:
        return sum(servicio_conteos.get(tid, 0) for tid in buckets.get(bucket, []))

    cap_bas = _sum_capitas("basico")
    cap_com = _sum_capitas("completo")
    cap_vip = _sum_capitas("vip")
    cap_87 = _sum_capitas("rama_87")
    cap_89 = _sum_capitas("rama_89")
    cap_90 = _sum_capitas("rama_90")
    cap_total = cap_bas + cap_com + cap_vip

    serv_bas = _sum_servicios("basico")
    serv_com = _sum_servicios("completo")
    serv_vip = _sum_servicios("vip")
    serv_total = serv_bas + serv_com + serv_vip

    def _coef(serv: int, cap: int) -> Decimal:
        if cap == 0:
            return Decimal("0")
        return (Decimal(serv) / Decimal(cap)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    coef_uso = _coef(serv_total, cap_total)

    if not alicuotas:
        coef_indice = Decimal("0")
    else:
        coeficientes = [Decimal(str(a.coeficiente)) for a in alicuotas]
        superiores = [c for c in coeficientes if c >= coef_uso]
        coef_indice = min(superiores) if superiores else max(coeficientes)

    def _valor_at(bucket: str) -> Decimal:
        tipo_ids = buckets.get(bucket, [])
        for a in alicuotas:
            if (
                a.tipo_servicio_id in tipo_ids
                and Decimal(str(a.coeficiente)) == coef_indice
            ):
                return Decimal(str(a.valor)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        return Decimal("0.00")

    valor_bas = _valor_at("basico")
    valor_com = _valor_at("completo")
    valor_vip = _valor_at("vip")

    total = (
        valor_bas * cap_bas + valor_com * cap_com + valor_vip * cap_vip
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return SintesisPeriodo(
        name=periodo.nombre,
        aumento=aumento,
        capitas_total=cap_total,
        capitas_basico=cap_bas,
        capitas_completo=cap_com,
        capitas_vip=cap_vip,
        capitas_rama_87=cap_87,
        capitas_rama_89=cap_89,
        capitas_rama_90=cap_90,
        servicios_total=serv_total,
        servicios_basico=serv_bas,
        servicios_completo=serv_com,
        servicios_vip=serv_vip,
        coef_uso=coef_uso,
        coef_uso_basico=_coef(serv_bas, cap_bas),
        coef_uso_completo=_coef(serv_com, cap_com),
        coef_uso_vip=_coef(serv_vip, cap_vip),
        coef_indice=coef_indice,
        valor_basico=valor_bas,
        valor_completo=valor_com,
        valor_vip=valor_vip,
        total=total,
    )


def _construir_snapshot(cuadro: SintesisPeriodo) -> dict:
    """Serialize the síntesis cuadro as the JSON-native cierre snapshot.

    The snapshot now carries ONLY the computed cuadro (capitas, service counts,
    coefficients, values and total). The raw input sheets live in
    ``periodo.hojas_entrada``, so the cierre no longer duplicates service rows.
    Decimals are serialized as fixed 2dp strings so ``json.dumps`` never sees a
    Decimal or date.
    """
    return {
        "nombre": cuadro.name,
        "aumento": _dec_str(cuadro.aumento),
        "capitas": {
            "total": cuadro.capitas_total,
            "basico": cuadro.capitas_basico,
            "completo": cuadro.capitas_completo,
            "vip": cuadro.capitas_vip,
            "rama_87": cuadro.capitas_rama_87,
            "rama_89": cuadro.capitas_rama_89,
            "rama_90": cuadro.capitas_rama_90,
        },
        "servicios": {
            "total": cuadro.servicios_total,
            "basico": cuadro.servicios_basico,
            "completo": cuadro.servicios_completo,
            "vip": cuadro.servicios_vip,
        },
        "coef_uso": str(cuadro.coef_uso),
        "coef_indice": str(cuadro.coef_indice),
        "valores": {
            "basico": _dec_str(cuadro.valor_basico),
            "completo": _dec_str(cuadro.valor_completo),
            "vip": _dec_str(cuadro.valor_vip),
        },
        "total_a_pagar": _dec_str(cuadro.total),
    }


async def cerrar_periodo(
    uow: UnitOfWorkPort,
    periodo_id: int,
    aumento: Decimal | float,
    motivo: str | None = None,
    servicio_conteos: dict[int, int] | None = None,
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

    creado, _ = await _cerrar_y_cascada(
        uow, target, dto, demote=False, servicio_conteos=servicio_conteos
    )
    await uow.commit()
    return creado


async def generar_nuevo_cierre(
    uow: UnitOfWorkPort,
    periodo_id: int,
    aumento: Decimal | float,
    motivo: str | None = None,
    servicio_conteos: dict[int, int] | None = None,
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

    creado, _ = await _cerrar_y_cascada(
        uow, target, dto, demote=True, servicio_conteos=servicio_conteos
    )
    await uow.commit()
    return creado


async def _cerrar_y_cascada(
    uow: UnitOfWorkPort,
    target: Periodo,
    dto: CreateCierre,
    *,
    demote: bool,
    servicio_conteos: dict[int, int] | None = None,
) -> tuple[Cierre, bool]:
    """Recalculate, (optionally) demote, and insert the cierre for ``target``.

    Alícuotas are sparse: they are only stored when the aumento is non-zero (a
    cambio). A zero aumento leaves the period with no alícuotas of its own, so it
    inherits the previous effective set. Returns ``(cierre, changed)`` where
    ``changed`` is True only when alícuotas were recalculated and stored (drives
    the cascade). Never commits: the caller owns the single atomic ``commit()``.
    """
    prev = await uow.periodos.get_previous(target.anio, target.mes)
    changed = False
    if prev is not None:
        prev_efectivas = await uow.alicuotas.get_effective(prev.anio, prev.mes)
        if dto.aumento != 0:
            recalculadas = recalcular_aumento(prev_efectivas, dto.aumento)
            nuevas = [
                a.model_copy(update={"periodo_id": target.id}) for a in recalculadas
            ]
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            changed = not _mismo_conjunto(nuevas, actuales)
            if changed:
                await uow.alicuotas.reemplazar_por_periodo(target.id, nuevas)
        else:
            # sin aumento no se guardan alícuotas propias: el periodo hereda
            actuales = await uow.alicuotas.get_by_keys(periodo_id=target.id)
            changed = len(actuales) > 0
            if changed:
                await uow.alicuotas.reemplazar_por_periodo(target.id, [])

    if demote:
        await uow.cierres.demote_oficial(target.id)

    snapshot = await _armar_snapshot(
        uow, target, dto.aumento, servicio_conteos=servicio_conteos
    )
    version = await uow.cierres.next_version(target.id)
    cierre = Cierre(
        periodo_id=target.id,
        version=version,
        estado=EstadoCierre.OFICIAL,
        origen=OrigenCierre.MANUAL,
        motivo=dto.motivo,
        aumento=dto.aumento,
        snapshot=snapshot,
    )
    creado = await uow.cierres.add(cierre)

    if changed:
        await _aplicar_cascada(uow, target, dto.motivo)
    return creado, changed


async def _aplicar_cascada(
    uow: UnitOfWorkPort, origen: Periodo, motivo_base: str | None
) -> None:
    """Re-close every later official period M in ascending ``(anio, mes)`` order.

    Each M is recalculated from its previous effective alicuotas by M's own
    ``aumento``, then demoted and re-inserted as ``origen=cascada``. Consistent
    with the sparse model, M only stores its own alicuotas when its aumento is
    non-zero; otherwise it inherits the previous effective set. Stops at the
    first later period without an official cierre. ``motivo_base`` is the reason
    on the origin cierre; cascaded cierres name the origin period instead.
    """
    for m in await uow.periodos.get_following(origen.anio, origen.mes):
        oficial_m = await uow.cierres.get_oficial(m.id)
        if oficial_m is None:
            break
        prev_m = await uow.periodos.get_previous(m.anio, m.mes)
        if prev_m is None:
            break
        prev_efectivas = await uow.alicuotas.get_effective(prev_m.anio, prev_m.mes)
        if oficial_m.aumento != 0:
            recalculadas = recalcular_aumento(prev_efectivas, oficial_m.aumento)
            nuevas = [a.model_copy(update={"periodo_id": m.id}) for a in recalculadas]
            await uow.alicuotas.reemplazar_por_periodo(m.id, nuevas)
        else:
            await uow.alicuotas.reemplazar_por_periodo(m.id, [])
        await uow.cierres.demote_oficial(m.id)
        snapshot_m = await _armar_snapshot(uow, m, oficial_m.aumento)
        version = await uow.cierres.next_version(m.id)
        await uow.cierres.add(
            Cierre(
                periodo_id=m.id,
                version=version,
                estado=EstadoCierre.OFICIAL,
                origen=OrigenCierre.CASCADA,
                motivo=f"cascada por {origen.nombre}",
                aumento=oficial_m.aumento,
                snapshot=snapshot_m,
            )
        )


async def _armar_snapshot(
    uow: UnitOfWorkPort,
    periodo: Periodo,
    aumento: Decimal,
    servicio_conteos: dict[int, int] | None = None,
) -> dict:
    """Build the síntesis cuadro snapshot for ``periodo`` from live tables.

    Refetches capitas, servicios, alicuotas and tipos inside the transaction so
    it sees the just-replaced alicuota set. Used by both closure paths. When
    ``servicio_conteos`` is injected it becomes the service-count source (so
    historical snapshots carry real counts even with an empty ``servicio`` table);
    otherwise counts derive from the ``servicio`` table as before.
    """
    capitas = await uow.capitas_periodo.get_by_fields(periodo_id=periodo.id)
    alicuotas = await uow.alicuotas.get_effective(periodo.anio, periodo.mes)
    servicios = await uow.servicios.get_by_fields(periodo_id=periodo.id)
    tipos_list = await uow.tipos_servicio.list()
    tipos = {t.id: t for t in tipos_list if t.id is not None}

    if servicio_conteos is not None:
        conteos = servicio_conteos
    else:
        conteos = Counter(s.tipo_servicio_id for s in servicios)
    cuadro = computar_sintesis(capitas, alicuotas, conteos, tipos, periodo, aumento)
    return _construir_snapshot(cuadro)


async def _cuadro_de_cierre(uow: UnitOfWorkPort, c: Cierre) -> dict:
    """Return a cierre's síntesis cuadro, recomputing on-demand when snapshot is null.

    Backward compatible: old snapshots wrapped the cuadro under ``"sintesis"``;
    new snapshots store the cuadro directly.
    """
    snapshot = c.snapshot
    if snapshot is not None:
        if isinstance(snapshot.get("sintesis"), dict):
            return snapshot["sintesis"]
        if isinstance(snapshot.get("capitas"), dict):
            return snapshot
    periodo = await uow.periodos.get(c.periodo_id)
    return await _armar_snapshot(uow, periodo, c.aumento)


async def armar_hoja_sintesis(
    uow: UnitOfWorkPort, anio: int, mes: int
) -> dict:
    """Return the current official cierre's cuadro plus up to 12 previous cuadros.

    Previous cuadros come from each cierre's snapshot; a prior cierre with a null
    snapshot is recomputed on-demand from tables (legacy parity). Ordered by
    descending recency.
    """
    periodos = await uow.periodos.get_by_anio_mes(anio, mes)
    if not periodos:
        return {"actual": None, "previos": []}
    target = periodos[0]

    oficial_actual = await uow.cierres.get_oficial(target.id)
    actual = (
        await _cuadro_de_cierre(uow, oficial_actual)
        if oficial_actual is not None
        else None
    )

    previos: list[dict] = []
    for c in await uow.cierres.get_oficiales_recientes(target.id, limit=12):
        previos.append(await _cuadro_de_cierre(uow, c))
    return {"actual": actual, "previos": previos}


async def descargar_cierre_excel(uow: UnitOfWorkPort, periodo_id: int) -> bytes:
    """Return the official cierre's SOS workbook (5 sheets) as xlsx bytes.

    Combines the period's input sheets (``periodo.hojas_entrada``) with the
    cierre's síntesis cuadro. Raises ``PeriodoNotClosedError`` when the period
    has no official cierre.
    """
    oficial = await uow.cierres.get_oficial(periodo_id)
    if oficial is None:
        raise PeriodoNotClosedError(periodo_id)
    periodo = await uow.periodos.get(periodo_id)
    cuadro = await _cuadro_de_cierre(uow, oficial)
    return exportar_cierre(periodo.hojas_entrada, cuadro, periodo.nombre).getvalue()
