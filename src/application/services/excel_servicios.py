"""Pure, sync Excel parser for the SOS service import (no DB).

Reads an .xlsx with ``openpyxl`` in read_only mode. Sheet 0 is the month
reference (validated for a single month), sheets 1-3 hold service rows and
sheet 4 (Síntesis) is ignored. The module has no I/O beyond the workbook, so it
is fully testable without a database.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, ConfigDict

from src.domain.enums import CategoriaServicio
from src.domain.exceptions import ImportServiciosError


class FilaServicio(BaseModel):
    model_config = ConfigDict(frozen=True)

    nro_servicio: str
    fecha: date
    dominio: str | None
    codigo_radio: str
    cod_productor: int
    hoja: str | None = None


# Fuzzy column aliases, keyed by the normalized FilaServicio field name. Headers
# are matched after ``normalizar_texto`` so tildes/case/whitespace never miss.
_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "nro_servicio": (
        "servicio",
        "nro servicio",
        "n servicio",
        "no servicio",
        "n de servicio",
        "numero servicio",
        "numero de servicio",
    ),
    "fecha": ("fecha",),
    "dominio": ("patente", "dominio", "dom"),
    "codigo_radio": ("codigo radio", "cod radio", "codigo", "radio", "producto"),
    "cod_productor": ("productor", "cod productor", "codigo productor", "numero de productor"),
}

_REQUIRED_COLUMNS = ("nro_servicio", "fecha", "dominio", "codigo_radio", "cod_productor")


def normalizar_texto(value: str) -> str:
    """NFKD + strip combining marks + lowercase + collapse whitespace.

    NFKD decomposes the ``º`` ordinal indicator to ``o``, so ``"Nº Servicio"``
    normalizes to ``"no servicio"`` (parity with the legacy
    ``utils.normalizar_texto``). The degree sign ``°`` (used by the legacy
    workbooks as ``"N°Servicio"``) is translated to a space first, so
    ``"N°Servicio"`` normalizes to ``"n servicio"``.
    """
    value = value.replace("\u00b0", " ")
    nfkd = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


_CODIGO_A_CATEGORIA = {
    "658": CategoriaServicio.VIP,
    "659": CategoriaServicio.BASICO,
    "660": CategoriaServicio.COMPLETO,
    "87": CategoriaServicio.RAMA_87,
    "89": CategoriaServicio.RAMA_89,
    "90": CategoriaServicio.RAMA_90,
}


def categoria_desde_hoja(hoja: str) -> CategoriaServicio | None:
    """Devuelve la categoría de cálculo según el prefijo numérico de la hoja.

    La hoja es la pista de resolución de un código desconocido:
    ``"659 Básico"`` -> ``BASICO``, ``"660 Completo"`` -> ``COMPLETO``,
    ``"658 Vip"`` -> ``VIP``. Devuelve ``None`` si la hoja no tiene un prefijo
    conocido (p. ej. ``"Síntesis"``).
    """
    match = re.match(r"^\s*(\d+)", hoja or "")
    if match is None:
        return None
    return _CODIGO_A_CATEGORIA.get(match.group(1))


def _sanitizar_dominio(value: str) -> str:
    """Upper-case and strip anything that is not alphanumeric or whitespace."""
    return re.sub(r"[^A-Z0-9\s]", "", value.upper())


def _to_date(value: Any) -> date:
    """Coerce a cell to a ``date`` (dayfirst for strings)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    raise ImportServiciosError(f"Fecha no reconocida: {value!r}")


def _coerce_int(value: Any) -> int:
    """Coerce a cell to int, tolerating ``"659.0"`` and float cells."""
    if isinstance(value, bool):
        raise ImportServiciosError(f"Valor numérico inválido: {value!r}")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ImportServiciosError(f"Valor numérico inválido: {value!r}") from exc


def _cell_str(value: Any) -> str:
    """Return the cell as a trimmed string, or ``""`` for empty cells."""
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return str(value).strip()


class ImportadorServiciosExcel:
    """Reads a SOS workbook and returns the normalized ``FilaServicio`` rows."""

    def leer(self, archivo: Path | BytesIO) -> list[FilaServicio]:
        wb = load_workbook(archivo, read_only=True, data_only=True)
        try:
            sheetnames = wb.sheetnames
            if len(sheetnames) != 5:
                raise ImportServiciosError(
                    f"Se esperaban 5 hojas, se encontraron {len(sheetnames)}"
                )

            self._validar_mes_unico(wb[sheetnames[0]])

            filas: list[FilaServicio] = []
            for name in sheetnames[1:4]:
                filas.extend(self._leer_hoja(wb[name], name))
            return filas
        finally:
            wb.close()

    def _validar_mes_unico(self, ws: Worksheet) -> None:
        """Fail when sheet 0 holds dates spanning more than one month."""
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        fecha_col = _find_column(header, ("fecha", "mes"))
        if fecha_col is None:
            return

        meses: set[tuple[int, int]] = set()
        for row in ws.iter_rows(min_row=2, min_col=fecha_col, max_col=fecha_col, values_only=True):
            value = row[0]
            if value in (None, ""):
                continue
            d = _to_date(value)
            meses.add((d.year, d.month))
        if len(meses) > 1:
            raise ImportServiciosError(
                "La hoja 0 (Mes) contiene fechas de más de un mes"
            )

    def _leer_hoja(self, ws: Worksheet, hoja: str) -> list[FilaServicio]:
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        mapping = _map_columns(header)
        missing = [c for c in _REQUIRED_COLUMNS if c not in mapping]
        if missing:
            raise ImportServiciosError(f"Columnas faltantes: {', '.join(missing)}")

        filas: list[FilaServicio] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            filas.append(self._fila_desde_row(row, mapping, hoja))
        return filas

    def _fila_desde_row(
        self, row: tuple, mapping: dict[str, int], hoja: str
    ) -> FilaServicio:
        nro = _cell_str(row[mapping["nro_servicio"] - 1]).strip().lower()
        if not nro:
            raise ImportServiciosError("Fila con número de servicio vacío")

        codigo_radio = _cell_str(row[mapping["codigo_radio"] - 1])
        if not codigo_radio:
            raise ImportServiciosError(f"Fila {nro!r} con código de radio vacío")
        codigo_radio = str(_coerce_int(codigo_radio))

        productor = _cell_str(row[mapping["cod_productor"] - 1])
        if not productor:
            raise ImportServiciosError(f"Fila {nro!r} con productor vacío")

        dominio_raw = _cell_str(row[mapping["dominio"] - 1])
        dominio = _sanitizar_dominio(dominio_raw) if dominio_raw else None

        return FilaServicio(
            nro_servicio=nro,
            fecha=_to_date(row[mapping["fecha"] - 1]),
            dominio=dominio,
            codigo_radio=codigo_radio,
            cod_productor=_coerce_int(productor),
            hoja=hoja,
        )


def _find_column(header: tuple, targets: tuple[str, ...]) -> int | None:
    """Return the 1-based index of the first header matching ``targets``."""
    for idx, cell in enumerate(header, start=1):
        if cell is None:
            continue
        if normalizar_texto(str(cell)) in targets:
            return idx
    return None


def _map_columns(header: tuple) -> dict[str, int]:
    """Map normalized headers to FilaServicio fields (fuzzy)."""
    normalized_aliases = {
        field: tuple(normalizar_texto(a) for a in aliases)
        for field, aliases in _COLUMN_ALIASES.items()
    }
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header, start=1):
        if cell is None:
            continue
        norm = normalizar_texto(str(cell))
        for field, aliases in normalized_aliases.items():
            if field not in mapping and norm in aliases:
                mapping[field] = idx
                break
    return mapping
