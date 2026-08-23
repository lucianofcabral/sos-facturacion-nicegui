"""Use cases for Cierre de Periodo.

``recalcular_aumento`` is a pure function (no I/O) so it can be unit-tested
without a database. Rounding uses Decimal ROUND_HALF_UP to two decimals; a
resulting valor <= 0 raises before any write happens.
"""

from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal

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
    Servicio,
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


_SHEET_KEYS = (
    "servicios_total",
    "servicios_basico",
    "servicios_completo",
    "servicios_vip",
)
_AUTOMOTORES_BUCKETS = ("basico", "completo", "vip")


def _normalizar_nombre(nombre: str) -> str:
    """NFKD + strip combining marks + casefold, so tildes/case never misclassify."""
    nfkd = unicodedata.normalize("NFKD", nombre)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).casefold()


def _clasificar_tipo(tipo: TipoServicio) -> str | None:
    """Classify a ``TipoServicio`` by its normalized name.

    Returns one of ``basico``/``completo``/``vip``/``rama_87``/``rama_89``/
    ``rama_90`` or ``None`` when the name matches no known bucket. Ramas are
    checked first because a rama name (e.g. "Rama 87") carries its own number.
    """
    nombre = _normalizar_nombre(tipo.nombre)
    if "87" in nombre:
        return "rama_87"
    if "89" in nombre:
        return "rama_89"
    if "90" in nombre:
        return "rama_90"
    if "basico" in nombre:
        return "basico"
    if "completo" in nombre:
        return "completo"
    if "vip" in nombre:
        return "vip"
    return None


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
        b = _clasificar_tipo(tipo)
        if b is not None:
            buckets.setdefault(b, []).append(tipo.id)

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
    cap_total = cap_bas + cap_com + cap_vip + cap_87 + cap_89 + cap_90

    serv_bas = _sum_servicios("basico")
    serv_com = _sum_servicios("completo")
    serv_vip = _sum_servicios("vip")
    serv_87 = _sum_servicios("rama_87")
    serv_89 = _sum_servicios("rama_89")
    serv_90 = _sum_servicios("rama_90")
    serv_total = serv_bas + serv_com + serv_vip + serv_87 + serv_89 + serv_90

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


def _construir_snapshot(
    servicios: list[Servicio],
    tipos: dict[int, TipoServicio],
    cuadro: SintesisPeriodo,
) -> dict:
    """Build the JSON-native 5-sheet snapshot (4 service sheets + síntesis).

    Service rows carry the full record (``fecha`` as ISO date, ``tipo`` as the
    raw tipo name) and the cuadro is serialized with Decimals as fixed 2dp
    strings, so ``json.dumps`` never sees a Decimal or date.
    """
    hojas: dict[str, list[dict]] = {k: [] for k in _SHEET_KEYS}

    def _fila(s: Servicio, tipo_nombre: str | None) -> dict:
        return {
            "nro_servicio": s.nro_servicio,
            "codigo_radio": s.codigo_radio,
            "fecha": s.fecha.isoformat(),
            "dominio": s.dominio,
            "cod_productor": s.cod_productor,
            "tipo": tipo_nombre,
        }

    for s in servicios:
        tipo = tipos.get(s.tipo_servicio_id)
        tipo_nombre = tipo.nombre if tipo is not None else None
        hojas["servicios_total"].append(_fila(s, tipo_nombre))
        if tipo is not None:
            bucket = _clasificar_tipo(tipo)
            if bucket in _AUTOMOTORES_BUCKETS:
                hojas[f"servicios_{bucket}"].append(_fila(s, tipo_nombre))

    sintesis = {
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
        "coef_uso": _dec_str(cuadro.coef_uso),
        "coef_indice": _dec_str(cuadro.coef_indice),
        "valores": {
            "basico": _dec_str(cuadro.valor_basico),
            "completo": _dec_str(cuadro.valor_completo),
            "vip": _dec_str(cuadro.valor_vip),
        },
        "total_a_pagar": _dec_str(cuadro.total),
    }

    return {
        "servicios_total": hojas["servicios_total"],
        "servicios_basico": hojas["servicios_basico"],
        "servicios_completo": hojas["servicios_completo"],
        "servicios_vip": hojas["servicios_vip"],
        "sintesis": sintesis,
    }


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
