"""Pure, sync Excel parser for the historical Panel.xlsm (no DB).

Reads the three sheets by name (``Inicial`` / ``SintesisH`` / ``Aumentos``) in
openpyxl read_only mode and returns a typed ``DatosPanel``. There is no I/O
beyond the workbook, so the module is fully testable without a database. Column
headers are matched after normalization (tildes/case/whitespace never miss),
mirroring the ``excel_servicios`` parser.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from src.domain.exceptions import PanelHistoricoError


def _normalizar(value: str) -> str:
    """NFKD + strip combining marks + lowercase + collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", value)
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


@dataclass(frozen=True)
class SintesisMes:
    """One month of the SintesisH sheet (capitas + service counts + ramas)."""

    c_basico: int
    c_completo: int
    c_vip: int
    s_basico: int
    s_completo: int
    s_vip: int
    r_87: int
    r_89: int
    r_90: int


@dataclass(frozen=True)
class DatosPanel:
    """Typed view of the historical workbook consumed by the seed CLI."""

    periodos: list[tuple[int, int]]
    alicuotas_iniciales: list[tuple[int, Decimal, Decimal]]
    sintesis: dict[tuple[int, int], SintesisMes]
    aumentos: dict[tuple[int, int], list[Decimal]]


# Fuzzy column aliases keyed by field name, matched after ``_normalizar``.
_INICIAL_COLUMNS: dict[str, tuple[str, ...]] = {
    "indice": ("indice", "coef", "coeficiente"),
    "prestacion": ("idprestacion", "id prestacion", "prestacion", "id"),
    "valor": ("valor",),
}

_SINTESIS_COLUMNS: dict[str, tuple[str, ...]] = {
    "periodo": ("periodo",),
    "c_basico": ("c_basico", "c basico", "capitas basico"),
    "c_completo": ("c_completo", "c completo", "capitas completo"),
    "c_vip": ("c_vip", "c vip", "capitas vip"),
    "s_basico": ("s_basico", "s basico", "servicios basico"),
    "s_completo": ("s_completo", "s completo", "servicios completo"),
    "s_vip": ("s_vip", "s vip", "servicios vip"),
    "r_87": ("r_87", "r 87", "rama 87"),
    "r_89": ("r_89", "r 89", "rama 89"),
    "r_90": ("r_90", "r 90", "rama 90"),
}

_AUMENTOS_COLUMNS: dict[str, tuple[str, ...]] = {
    "fecha": ("fecha",),
    "aumento": ("aumento",),
}

_SINTESIS_REQUIRED = (
    "periodo",
    "c_basico",
    "c_completo",
    "c_vip",
    "s_basico",
    "s_completo",
    "s_vip",
    "r_87",
    "r_89",
    "r_90",
)


def _find_sheet(wb, name_aliases: tuple[str, ...]) -> Worksheet:
    """Return the first sheet whose normalized name matches an alias."""
    for name in wb.sheetnames:
        norm = _normalizar(name)
        if any(norm == _normalizar(a) for a in name_aliases):
            return wb[name]
    raise PanelHistoricoError(f"Hoja no encontrada: {name_aliases[0]!r}")


def _map_columns(
    header: tuple, aliases: dict[str, tuple[str, ...]]
) -> dict[str, int]:
    """Map normalized headers to field names (fuzzy)."""
    normalized = {
        field: tuple(_normalizar(a) for a in als)
        for field, als in aliases.items()
    }
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(header, start=1):
        if cell is None:
            continue
        norm = _normalizar(str(cell))
        for field, als in normalized.items():
            if field not in mapping and norm in als:
                mapping[field] = idx
                break
    return mapping


def _to_decimal(value: Any, what: str) -> Decimal:
    if value in (None, ""):
        raise PanelHistoricoError(f"{what}: valor vacío")
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise PanelHistoricoError(f"{what}: valor no numérico {value!r}") from exc


def _to_int(value: Any, what: str) -> int:
    if value in (None, ""):
        raise PanelHistoricoError(f"{what}: valor vacío")
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise PanelHistoricoError(f"{what}: valor no numérico {value!r}") from exc


def _to_anio_mes(value: Any) -> tuple[int, int]:
    """Coerce a Periodo/Fecha cell to ``(anio, mes)``."""
    if isinstance(value, datetime):
        return value.year, value.month
    if isinstance(value, date):
        return value.year, value.month
    if isinstance(value, str):
        s = value.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m"):
            try:
                d = datetime.strptime(s, fmt)
                return d.year, d.month
            except ValueError:
                continue
    raise PanelHistoricoError(f"Fecha no reconocida: {value!r}")


class ParserPanelHistorico:
    """Reads the historical Panel workbook and returns a typed ``DatosPanel``."""

    def leer(self, archivo: Path | BytesIO) -> DatosPanel:
        wb = load_workbook(archivo, read_only=True, data_only=True)
        try:
            ws_inicial = _find_sheet(wb, ("inicial",))
            ws_sintesis = _find_sheet(wb, ("sintesish", "sintesis h"))
            ws_aumentos = _find_sheet(wb, ("aumentos",))

            alicuotas = self._leer_inicial(ws_inicial)
            periodos, sintesis = self._leer_sintesis(ws_sintesis)
            aumentos = self._leer_aumentos(ws_aumentos)
            return DatosPanel(
                periodos=periodos,
                alicuotas_iniciales=alicuotas,
                sintesis=sintesis,
                aumentos=aumentos,
            )
        finally:
            wb.close()

    def _leer_inicial(
        self, ws: Worksheet
    ) -> list[tuple[int, Decimal, Decimal]]:
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        mapping = _map_columns(header, _INICIAL_COLUMNS)
        for req in ("indice", "prestacion", "valor"):
            if req not in mapping:
                raise PanelHistoricoError(f"Inicial: columna faltante {req!r}")

        filas: list[tuple[int, Decimal, Decimal]] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            indice = row[mapping["indice"] - 1]
            if indice in (None, ""):
                continue
            coef = _to_decimal(indice, "Indice")
            prest = _to_int(row[mapping["prestacion"] - 1], "idPrestacion")
            valor = _to_decimal(row[mapping["valor"] - 1], "Valor")
            filas.append((prest, coef, valor))
        return filas

    def _leer_sintesis(
        self, ws: Worksheet
    ) -> tuple[list[tuple[int, int]], dict[tuple[int, int], SintesisMes]]:
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        mapping = _map_columns(header, _SINTESIS_COLUMNS)
        for req in _SINTESIS_REQUIRED:
            if req not in mapping:
                raise PanelHistoricoError(f"SintesisH: columna faltante {req!r}")

        periodos: list[tuple[int, int]] = []
        sintesis: dict[tuple[int, int], SintesisMes] = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            periodo_val = row[mapping["periodo"] - 1]
            if periodo_val in (None, ""):
                continue
            anio, mes = _to_anio_mes(periodo_val)

            def _g(field: str) -> int:
                return _to_int(row[mapping[field] - 1], field)

            mes_datos = SintesisMes(
                c_basico=_g("c_basico"),
                c_completo=_g("c_completo"),
                c_vip=_g("c_vip"),
                s_basico=_g("s_basico"),
                s_completo=_g("s_completo"),
                s_vip=_g("s_vip"),
                r_87=_g("r_87"),
                r_89=_g("r_89"),
                r_90=_g("r_90"),
            )
            periodos.append((anio, mes))
            sintesis[(anio, mes)] = mes_datos
        return periodos, sintesis

    def _leer_aumentos(self, ws: Worksheet) -> dict[tuple[int, int], list[Decimal]]:
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        mapping = _map_columns(header, _AUMENTOS_COLUMNS)
        for req in ("fecha", "aumento"):
            if req not in mapping:
                raise PanelHistoricoError(f"Aumentos: columna faltante {req!r}")

        aumentos: dict[tuple[int, int], list[Decimal]] = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row is None or all(v in (None, "") for v in row):
                continue
            fecha_val = row[mapping["fecha"] - 1]
            if fecha_val in (None, ""):
                continue
            anio, mes = _to_anio_mes(fecha_val)
            aumento = _to_decimal(row[mapping["aumento"] - 1], "Aumento")
            aumentos.setdefault((anio, mes), []).append(aumento)
        return aumentos
