"""Pure SOS workbook export for a cierre (no DB).

Rebuilds the 5-sheet SOS layout: the 4 input data sheets replay verbatim from
``periodo.hojas_entrada`` (17-column rows) and the ``Síntesis`` sheet holds the
computed cuadro using the legacy report layout for a single period. Fully
testable without a database.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Border, Font, Side
from openpyxl.utils import get_column_letter

_TIPO_SHEET_NAMES = ("659 Básico", "660 Completo", "658 Vip")

# Formatos legacy del reporte SOS (reporte_202607.xlsx).
_PERC_FORMAT = "0.00%"
_MONEY_FORMAT = "$ #,###,##0.00"
_COUNT_FORMAT = "#,###,##0"

# Ancho de las columnas E..P en la hoja Síntesis (mismo que el reporte legacy).
_SINTESIS_COL_WIDTH = 19

_THIN = Side(style="thin")
_BORDER_SIDES = {"L": "left", "R": "right", "T": "top", "B": "bottom"}

# Grilla de bordes del cuadro legacy: (fila, col) -> lados con borde fino.
# Filas 0-8 = r2-r10, cols 0-8 = E-M. Replicado de reporte_202607.xlsx.
_BORDES_CUADRO: dict[tuple[int, int], str] = {
    (0, 0): "LT", (0, 1): "T", (0, 2): "T", (0, 3): "T", (0, 4): "T",
    (0, 5): "T", (0, 6): "T", (0, 7): "T", (0, 8): "RT",
    (1, 0): "LB", (1, 1): "B", (1, 2): "B", (1, 3): "B", (1, 4): "B",
    (1, 5): "B", (1, 6): "B", (1, 7): "B", (1, 8): "RB",
    (2, 0): "L", (2, 1): "LRT", (2, 2): "T", (2, 3): "T", (2, 4): "RT",
    (2, 5): "LRT", (2, 6): "T", (2, 7): "T", (2, 8): "RT",
    (3, 0): "L", (3, 1): "L", (3, 4): "R", (3, 5): "L", (3, 8): "R",
    (4, 0): "L", (4, 1): "LB", (4, 2): "B", (4, 3): "B", (4, 4): "RB",
    (4, 5): "LB", (4, 6): "B", (4, 7): "B", (4, 8): "RB",
    (5, 0): "L", (5, 1): "LRT", (5, 2): "T", (5, 3): "T", (5, 4): "RT",
    (5, 5): "R", (5, 8): "R",
    (6, 0): "L", (6, 1): "L", (6, 4): "R", (6, 8): "R",
    (7, 0): "L", (7, 1): "L", (7, 4): "R", (7, 5): "RB", (7, 8): "R",
    (8, 0): "LB", (8, 1): "LB", (8, 2): "B", (8, 3): "B", (8, 4): "RB",
    (8, 5): "B", (8, 6): "B", (8, 7): "B", (8, 8): "RB",
}


def _borde_cuadro(spec: str) -> Border:
    return Border(**{_BORDER_SIDES[ch]: _THIN for ch in spec})


def _dec(value: object) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _int(value: object) -> int:
    return int(_dec(value))


def _reproducir_hojas(
    wb: Workbook, hojas_entrada: dict | None, periodo_nombre: str
) -> None:
    """Replay the 4 input sheets (headers + rows) verbatim from ``hojas_entrada``.

    Falls back to empty sheets with the expected names when no input sheets are
    stored (e.g. historical periods imported before the capture existed).
    """
    hojas = (hojas_entrada or {}).get("hojas")
    if not isinstance(hojas, list) or not hojas:
        wb.create_sheet(periodo_nombre[:31])
        for name in _TIPO_SHEET_NAMES:
            wb.create_sheet(name)
        return

    for hoja in hojas:
        ws = wb.create_sheet(str(hoja.get("nombre") or "")[:31])
        ws.append(list(hoja.get("encabezados", [])))
        for fila in hoja.get("filas", []):
            ws.append(list(fila))


def _escribir_cuadro(
    ws, sintesis: dict, periodo_nombre: str, row0: int = 2
) -> None:
    """Write the single-period síntesis cuadro in the legacy report layout.

    Cobertura A = cápitas básicas (the legacy put the total there), B = completa,
    C = vip. Values are already 2dp. ``row0`` lets callers stack several blocks
    (one per period) on the same sheet.
    """
    cap = sintesis.get("capitas", {})
    ser = sintesis.get("servicios", {})
    val = sintesis.get("valores", {})

    cap_bas = _int(cap.get("basico"))
    cap_com = _int(cap.get("completo"))
    cap_vip = _int(cap.get("vip"))
    cap_total = _int(cap.get("total", cap_bas + cap_com + cap_vip))
    rama_87 = _int(cap.get("rama_87"))
    rama_89 = _int(cap.get("rama_89"))
    rama_90 = _int(cap.get("rama_90"))

    ser_bas = _int(ser.get("basico"))
    ser_com = _int(ser.get("completo"))
    ser_vip = _int(ser.get("vip"))
    ser_total = _int(ser.get("total", ser_bas + ser_com + ser_vip))

    coef_uso = _dec(sintesis.get("coef_uso"))
    coef_indice = _dec(sintesis.get("coef_indice"))

    valor_bas = _dec(val.get("basico"))
    valor_com = _dec(val.get("completo"))
    valor_vip = _dec(val.get("vip"))
    total = valor_bas * cap_bas + valor_com * cap_com + valor_vip * cap_vip

    col0 = 5  # column E

    def celda(
        r: int, c: int, valor: object, fmt: str | None = None, bold: bool = False
    ) -> None:
        cell = ws.cell(row=row0 + r, column=col0 + c, value=valor)
        if fmt is not None:
            cell.number_format = fmt
        if bold:
            cell.font = Font(bold=True)
        return cell

    def merge(r: int, c1: int, c2: int, r2: int | None = None) -> None:
        ws.merge_cells(
            start_row=row0 + r, start_column=col0 + c1,
            end_row=row0 + (r if r2 is None else r2), end_column=col0 + c2,
        )

    # Fila 0: encabezados
    celda(0, 0, "AUTOS")
    merge(0, 10, 11)
    celda(0, 10, "CÁPITAS INFORMADAS", bold=True)
    # Fila 1
    celda(1, 10, "AUTOMOTORES:")
    # Fila 2: periodo + encabezados principales + Cobertura A
    celda(2, 0, periodo_nombre)
    merge(2, 1, 4)
    celda(2, 1, "VEHICULOS A RIESGO")
    merge(2, 5, 8)
    celda(2, 5, "SERVICIOS")
    celda(2, 10, "Cobertura A:")
    celda(2, 11, cap_bas, fmt=_COUNT_FORMAT)
    # Fila 3: encabezados de columnas + Cobertura B
    celda(3, 0, "coef. de uso")
    celda(3, 1, "TOTAL CAPITAS")
    celda(3, 2, "Básica")
    celda(3, 3, "Completa")
    celda(3, 4, "VIP")
    celda(3, 5, "TOTAL SERVICIOS")
    celda(3, 6, "Básica")
    celda(3, 7, "Completa")
    celda(3, 8, "VIP")
    celda(3, 10, "Cobertura B:")
    celda(3, 11, cap_com, fmt=_COUNT_FORMAT)
    # Fila 4: datos principales + Cobertura C
    celda(4, 0, float(coef_uso), fmt=_PERC_FORMAT)
    celda(4, 1, cap_total, fmt=_COUNT_FORMAT)
    celda(4, 2, cap_bas, fmt=_COUNT_FORMAT)
    celda(4, 3, cap_com, fmt=_COUNT_FORMAT)
    celda(4, 4, cap_vip, fmt=_COUNT_FORMAT)
    celda(4, 5, ser_total, fmt=_COUNT_FORMAT)
    celda(4, 6, ser_bas, fmt=_COUNT_FORMAT)
    celda(4, 7, ser_com, fmt=_COUNT_FORMAT)
    celda(4, 8, ser_vip, fmt=_COUNT_FORMAT)
    celda(4, 10, "Cobertura C:")
    celda(4, 11, cap_vip, fmt=_COUNT_FORMAT)
    # Fila 5: TOTAL A PAGAR / ALICUOTAS / RAMAS
    merge(5, 1, 4)
    celda(5, 1, "ALICUOTAS CORRESPONDIENTES")
    merge(5, 5, 8, r2=6)
    celda(5, 5, f"TOTAL A PAGAR POR AUTOS - {periodo_nombre}".upper(), bold=True)
    celda(5, 10, "RAMAS VARIAS:")
    # Fila 6: coeficiente + encabezados + Rama 87
    celda(6, 0, float(coef_indice), fmt=_PERC_FORMAT)
    celda(6, 2, "Básica")
    celda(6, 3, "Completa")
    celda(6, 4, "VIP")
    celda(6, 10, "Rama 87:")
    celda(6, 11, rama_87, fmt=_COUNT_FORMAT)
    # Fila 7: valores + total + Rama 89
    celda(7, 2, float(valor_bas), fmt=_MONEY_FORMAT)
    celda(7, 3, float(valor_com), fmt=_MONEY_FORMAT)
    celda(7, 4, float(valor_vip), fmt=_MONEY_FORMAT)
    merge(7, 5, 8, r2=8)
    celda(7, 5, float(total), fmt=_MONEY_FORMAT, bold=True)
    celda(7, 10, "Rama 89:")
    celda(7, 11, rama_89, fmt=_COUNT_FORMAT)
    # Fila 8: subtotales + Rama 90
    celda(8, 2, float(valor_bas * cap_bas), fmt=_MONEY_FORMAT, bold=True)
    celda(8, 3, float(valor_com * cap_com), fmt=_MONEY_FORMAT, bold=True)
    celda(8, 4, float(valor_vip * cap_vip), fmt=_MONEY_FORMAT, bold=True)
    celda(8, 10, "Rama 90:")
    celda(8, 11, rama_90, fmt=_COUNT_FORMAT)

    # Bordes finos del cuadro legacy (grilla 9x9).
    for (r, c), spec in _BORDES_CUADRO.items():
        ws.cell(row=row0 + r, column=col0 + c).border = _borde_cuadro(spec)


def exportar_cierre(
    hojas_entrada: dict | None,
    sintesis: dict,
    periodo_nombre: str,
    previos: list[dict] | None = None,
) -> BytesIO:
    """Build the 5-sheet SOS workbook (input sheets + síntesis cuadro).

    ``previos`` renders one extra cuadro block per previous cierre below the
    current one, matching the legacy report's "cuadro de los 12 cierres
    anteriores". Each block uses a 10-row stride (9 content rows + 1 blank) and
    the previous cierre's own ``nombre`` as its title.
    """
    wb = Workbook()
    wb.remove(wb.active)

    _reproducir_hojas(wb, hojas_entrada, periodo_nombre)

    ws_sintesis = wb.create_sheet("Síntesis")
    for idx in range(5, 17):  # columnas E..P
        ws_sintesis.column_dimensions[get_column_letter(idx)].width = _SINTESIS_COL_WIDTH
    _escribir_cuadro(ws_sintesis, sintesis, periodo_nombre)
    for idx, previo in enumerate(previos or (), start=1):
        _escribir_cuadro(
            ws_sintesis,
            previo,
            str(previo.get("nombre") or f"previo {idx}"),
            row0=2 + idx * 10,
        )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
