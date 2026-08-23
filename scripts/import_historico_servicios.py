"""One-off CLI: import histórico de servicios 2014-2025 (no UI).

Usage::

    uv run scripts/import_historico_servicios.py --dry-run
    uv run scripts/import_historico_servicios.py

Recorre cada workbook mensual bajo ``--base`` (default ``migrations/files``),
convierte los ``.xls`` legados vía LibreOffice headless, determina el
(anio, mes) desde la hoja 0, y re-importa cada mes en ``servicio`` mediante
``importar_servicios`` (modo ``reemplazo``). Los meses sin archivo y los
archivos que no parsean se reportan, no abortan la corrida.

Soporta ambos formatos:
- moderno (2019+): columna ``Codigo Radio``.
- viejo (2014-2018): columna ``Producto`` (código) + ``Número de Productor``.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# isort: off
from openpyxl import load_workbook  # noqa: E402
from src.application.services.excel_servicios import (  # noqa: E402
    ImportadorServiciosExcel,
    _find_column,
    _to_date,
)
from src.application.use_cases import servicio as servicio_uc  # noqa: E402
from src.domain.enums import RolUsuario  # noqa: E402
from src.infrastructure.adapters.uow import PostgresUoW  # noqa: E402
# isort: on

_MESES_ES = (
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
)


class ImportHistoricoError(Exception):
    """Raised when the import cannot proceed (fase global fallida)."""


def _convertir_xls(xls: Path, outdir: Path) -> Path:
    """Convierte un .xls a .xlsx con LibreOffice headless; devuelve la ruta nueva."""
    subprocess.run(
        [
            "soffice", "--headless", "--convert-to", "xlsx",
            "--outdir", str(outdir), str(xls),
        ],
        check=True,
        capture_output=True,
    )
    return outdir / (xls.stem + ".xlsx")


def _mes_anio_de_hoja0(xlsx: Path) -> tuple[int, int]:
    """Devuelve (anio, mes) leyendo la primera fecha de la hoja 0."""
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        col = _find_column(header, ("fecha", "mes"))
        if col is None:
            raise ImportHistoricoError(f"hoja 0 sin columna fecha: {xlsx.name}")
        for row in ws.iter_rows(min_row=2, min_col=col, max_col=col, values_only=True):
            value = row[0]
            if value in (None, ""):
                continue
            d = _to_date(value)
            return (d.year, d.month)
    finally:
        wb.close()
    raise ImportHistoricoError(f"hoja 0 sin fechas: {xlsx.name}")


def _inventario(base: Path, convert_dir: Path, skip: tuple[str, ...]) -> list[tuple[Path, int, int]]:
    """Devuelve [(ruta_xlsx, anio, mes)] ordenados cronológicamente, sin duplicados.

    Los .xls se convierten a ``convert_dir``; los archivos cuyo nombre contiene
    algún fragmento de ``skip`` (p. ej. ``tarifa_vieja``) se descartan.
    """
    items: list[tuple[Path, int, int]] = []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix not in (".xlsx", ".xls"):
            continue
        if any(s in p.name for s in skip):
            continue
        xlsx = p if p.suffix == ".xlsx" else _convertir_xls(p, convert_dir)
        anio, mes = _mes_anio_de_hoja0(xlsx)
        items.append((xlsx, anio, mes))
    items.sort(key=lambda t: (t[1], t[2]))
    return items


def _plan(items: list[tuple[Path, int, int]]) -> dict:
    """Parse de todos los archivos (sin DB) para el plan/dry-run."""
    lector = ImportadorServiciosExcel()
    detalle: list[dict] = []
    for xlsx, anio, mes in items:
        filas = lector.leer(xlsx)
        codigos: dict[str, int] = {}
        for f in filas:
            codigos[f.codigo_radio] = codigos.get(f.codigo_radio, 0) + 1
        detalle.append(
            {"anio": anio, "mes": mes, "filas": len(filas), "codigos": codigos}
        )
    return {"archivos": len(detalle), "filas_total": sum(d["filas"] for d in detalle), "detalle": detalle}


async def ejecutar_import(items: list[tuple[Path, int, int]], *, dry_run: bool) -> dict:
    """Importa cada archivo en su periodo (reemplazo). Devuelve un resumen."""
    if dry_run:
        return {"dry_run": True, **_plan(items)}

    resultado: list[dict] = []
    total_creados = 0
    for xlsx, anio, mes in items:
        async with PostgresUoW() as uow:
            periodos = await uow.periodos.get_by_anio_mes(anio, mes)
            if not periodos:
                resultado.append(
                    {"anio": anio, "mes": mes, "error": f"sin periodo {anio}-{mes}"}
                )
                continue
            periodo_id = periodos[0].id
            try:
                res = await servicio_uc.importar_servicios(
                    uow, periodo_id, xlsx, "reemplazo", rol=RolUsuario.ADMIN
                )
            except Exception as exc:  # un archivo malo no aborta la corrida
                await uow.rollback()
                resultado.append(
                    {"anio": anio, "mes": mes, "error": f"{type(exc).__name__}: {exc}"}
                )
                continue
        total_creados += res["creados"]
        resultado.append(
            {
                "anio": anio,
                "mes": mes,
                "creados": res["creados"],
                "eliminados": res["eliminados"],
                "pendientes": res["pendientes"],
            }
        )

    errores = [r for r in resultado if "error" in r]
    return {
        "dry_run": False,
        "meses": len(resultado),
        "total_creados": total_creados,
        "errores": errores,
        "detalle": resultado,
    }


def _resumen(r: dict) -> str:
    if r["dry_run"]:
        lineas = [f"DRY-RUN: {r['archivos']} archivos, {r['filas_total']} filas en total"]
        for d in r["detalle"]:
            lineas.append(
                f"  {d['anio']}-{d['mes']:02d}: {d['filas']} filas {d['codigos']}"
            )
        return "\n".join(lineas)

    lineas = [
        f"Import completado: {r['meses']} meses, {r['total_creados']} servicios insertados."
    ]
    pendientes_total = sum(len(d["pendientes"]) for d in r["detalle"] if "pendientes" in d)
    if pendientes_total:
        lineas.append(f"  ATENCION: {pendientes_total} grupos pendientes")
        for d in r["detalle"]:
            if d.get("pendientes"):
                lineas.append(f"  {d['anio']}-{d['mes']:02d}: {d['pendientes']}")
    if r["errores"]:
        lineas.append(f"  {len(r['errores'])} errores:")
        for e in r["errores"]:
            lineas.append(f"    {e['anio']}-{e['mes']:02d}: {e['error']}")
    return "\n".join(lineas)


async def _run(base: Path, convert_dir: Path, skip: tuple[str, ...], dry_run: bool) -> None:
    items = _inventario(base, convert_dir, skip)
    print(f"Inventario: {len(items)} archivos a procesar.")
    print(_resumen(await ejecutar_import(items, dry_run=dry_run)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import histórico de servicios 2014-2025")
    parser.add_argument(
        "--base",
        default="/home/fexa/R/fapi/migrations/files",
        help="directorio base con archivos por año (default: %(default)s)",
    )
    parser.add_argument(
        "--skip",
        default="tarifa_vieja",
        help="fragmentos de nombre a descartar, separados por coma (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="parse + plan sin escribir")
    args = parser.parse_args()
    skip = tuple(s.strip() for s in args.skip.split(",") if s.strip())
    with tempfile.TemporaryDirectory(prefix="conv_servicios_") as tmp:
        asyncio.run(_run(Path(args.base), Path(tmp), skip, args.dry_run))


if __name__ == "__main__":
    main()
