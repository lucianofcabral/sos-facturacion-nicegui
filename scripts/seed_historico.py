"""One-off CLI: seed historical facturación from Panel.xlsm (no UI).

Usage::

    uv run scripts/seed_historico.py [--xlsx PATH] [--dry-run]

Reads ``Inicial``/``SintesisH``/``Aumentos`` via the pure parser, then writes
through ``PostgresUoW`` in committed phases (tipos -> periodos -> alicuotas
jul-2014 -> cápitas -> replay de aumentos como cierres). Idempotency guard:
aborts if any periodo with ``anio`` in [2014, 2025] already exists.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# isort: off
from src.application.services.panel_historico import DatosPanel, ParserPanelHistorico  # noqa: E402
from src.application.use_cases import cierre  # noqa: E402
from src.domain.models.entities import (  # noqa: E402
    Alicuota,
    CapitaPeriodo,
    Periodo,
    TipoServicio,
)
from src.infrastructure.adapters.uow import PostgresUoW  # noqa: E402
# isort: on

_MESES_ES = (
    "ENERO",
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
    "JUNIO",
    "JULIO",
    "AGOSTO",
    "SEPTIEMBRE",
    "OCTUBRE",
    "NOVIEMBRE",
    "DICIEMBRE",
)

# Seeded tipos: (nombre, rama, codigo). Names must match `_clasificar_tipo`.
_TIPOS = (
    ("Básico", "Automotores", "659"),
    ("Completo", "Automotores", "660"),
    ("VIP", "Automotores", "658"),
    ("Rama 87", "Ramas Varias", "87"),
    ("Rama 89", "Ramas Varias", "89"),
    ("Rama 90", "Ramas Varias", "90"),
)

# Inicial idPrestacion -> tipo_servicio nombre.
_PRESTACION_A_TIPO = {1: "Básico", 2: "Completo", 3: "VIP"}

_DRIFT_NOTE = (
    "Drift 2dp aceptado vs legacy (ROUND_HALF_UP mensual): Básica coef 0.03 -> "
    "1463.61 vs legacy 1463.87. Única ruta autoconsistente con NUMERIC(12,2)."
)


class SeedHistoricoError(Exception):
    """Raised when the seed cannot proceed (idempotency guard / phase failure)."""


def _plan(datos: DatosPanel) -> dict:
    aumentos = sum(len(v) for v in datos.aumentos.values())
    return {
        "tipos": len(_TIPOS),
        "periodos": len(datos.periodos),
        "alicuotas": len(datos.alicuotas_iniciales),
        "capitas": 6 * len(datos.periodos),
        "aumentos": aumentos,
        "cierres": len(datos.periodos),
        "cierres_filas": len(datos.periodos)
        + sum(max(0, len(v) - 1) for v in datos.aumentos.values()),
    }


async def ejecutar_seed(datos: DatosPanel, *, dry_run: bool = False) -> dict:
    """Seed the DB from a parsed ``DatosPanel`` in committed phases.

    ``dry_run`` parses + plans with zero writes (no DB connection). The real run
    aborts via ``SeedHistoricoError`` if any periodo in [2014, 2025] exists.
    """
    plan = _plan(datos)
    if dry_run:
        return {"dry_run": True, **plan}

    async with PostgresUoW() as uow:
        # Idempotency guard: rollback first if the historical range is present.
        for anio in range(2014, 2026):
            if await uow.periodos.get_by_anio(anio):
                raise SeedHistoricoError(
                    f"Ya existen periodos para anio={anio}. Rollback primero: "
                    "DELETE FROM periodo WHERE anio < 2024 (cascada limpia)."
                )

        # fase 1: 6 tipos de servicio
        tipo_ids: dict[str, int] = {}
        for nombre, rama, codigo in _TIPOS:
            t = await uow.tipos_servicio.add(
                TipoServicio(rama=rama, nombre=nombre, codigo=codigo)
            )
            assert t.id is not None
            tipo_ids[nombre] = t.id
        await uow.commit()

        # fase 2: 136 periodos contiguos
        periodo_ids: dict[tuple[int, int], int] = {}
        for anio, mes in datos.periodos:
            nombre = f"{_MESES_ES[mes - 1]} {anio}"
            p = await uow.periodos.add(Periodo(nombre=nombre, anio=anio, mes=mes))
            assert p.id is not None
            periodo_ids[(anio, mes)] = p.id
        await uow.commit()

        # fase 3: 108 alicuotas jul-2014 (36 coef x 3 prestaciones)
        primer = datos.periodos[0]
        for prest, coef, valor in datos.alicuotas_iniciales:
            await uow.alicuotas.add(
                Alicuota(
                    periodo_id=periodo_ids[primer],
                    tipo_servicio_id=tipo_ids[_PRESTACION_A_TIPO[prest]],
                    coeficiente=float(coef),
                    valor=float(valor),
                )
            )
        await uow.commit()

        # fase 4: 6 capitas x 136 periodos
        for anio, mes in datos.periodos:
            sint = datos.sintesis[(anio, mes)]
            filas = (
                ("Básico", sint.c_basico),
                ("Completo", sint.c_completo),
                ("VIP", sint.c_vip),
                ("Rama 87", sint.r_87),
                ("Rama 89", sint.r_89),
                ("Rama 90", sint.r_90),
            )
            for nombre, capitas in filas:
                await uow.capitas_periodo.add(
                    CapitaPeriodo(
                        periodo_id=periodo_ids[(anio, mes)],
                        tipo_servicio_id=tipo_ids[nombre],
                        capitas=capitas,
                    )
                )
        await uow.commit()

        # fase 5: replay de aumentos como cierres (per-period commit)
        for anio, mes in datos.periodos:
            sint = datos.sintesis[(anio, mes)]
            conteos = {
                tipo_ids["Básico"]: sint.s_basico,
                tipo_ids["Completo"]: sint.s_completo,
                tipo_ids["VIP"]: sint.s_vip,
            }
            aumentos = datos.aumentos.get((anio, mes), [])
            a1 = aumentos[0] if aumentos else Decimal("0")
            await cierre.cerrar_periodo(
                uow, periodo_ids[(anio, mes)], a1, servicio_conteos=conteos
            )
            for a2 in aumentos[1:]:
                await cierre.generar_nuevo_cierre(
                    uow, periodo_ids[(anio, mes)], a2, servicio_conteos=conteos
                )

    return {"dry_run": False, **plan}


def _resumen(resultado: dict) -> str:
    etiqueta = "DRY-RUN (plan)" if resultado["dry_run"] else "Seed completado"
    return "\n".join(
        [
            f"{etiqueta}:",
            f"  tipos: {resultado['tipos']}",
            f"  periodos: {resultado['periodos']}",
            f"  alicuotas (jul-2014): {resultado['alicuotas']}",
            f"  capitas: {resultado['capitas']}",
            f"  aumentos: {resultado['aumentos']}",
            f"  cierres: {resultado['cierres']} oficiales "
            f"({resultado['cierres_filas']} filas con 2022-08 x2)",
            _DRIFT_NOTE,
        ]
    )


async def _run(xlsx: Path, dry_run: bool) -> None:
    datos = ParserPanelHistorico().leer(xlsx)
    resultado = await ejecutar_seed(datos, dry_run=dry_run)
    print(_resumen(resultado))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed histórico desde Panel.xlsm")
    parser.add_argument(
        "--xlsx",
        default="/home/fexa/R/fapi/migrations/Panel.xlsm",
        help="ruta al Panel.xlsm (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="parse + plan sin escribir nada",
    )
    args = parser.parse_args()
    asyncio.run(_run(Path(args.xlsx), args.dry_run))


if __name__ == "__main__":
    main()
