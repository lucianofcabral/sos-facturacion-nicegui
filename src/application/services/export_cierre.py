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

_TIPO_SHEET_NAMES = ("659 Básico", "660 Completo", "658 Vip")

_PERC_FORMAT = "0.00%"
_MONEY_FORMAT = "#,##0.00"
_COUNT_FORMAT = "#,##0"


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


def _escribir_cuadro(ws, sintesis: dict, periodo_nombre: str) -> None:
    """Write the single-period síntesis cuadro in the legacy report layout.

    Cobertura A = cápitas básicas (the legacy put the total there), B = completa,
    C = vip. Values are already 2dp.
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

    row0 = 2
    col0 = 5  # column E

    def celda(r: int, c: int, valor: object) -> None:
        ws.cell(row=row0 + r, column=col0 + c, value=valor)

    def merge(r: int, c1: int, c2: int) -> None:
        ws.merge_cells(
            start_row=row0 + r, start_column=col0 + c1,
            end_row=row0 + r, end_column=col0 + c2,
        )

    # Fila 0: encabezados
    celda(0, 0, "AUTOS")
    merge(0, 10, 11)
    celda(0, 10, "CÁPITAS INFORMADAS")
    # Fila 1
    celda(1, 10, "AUTOMOTORES:")
    # Fila 2: periodo + encabezados principales + Cobertura A
    celda(2, 0, periodo_nombre)
    merge(2, 1, 4)
    celda(2, 1, "VEHICULOS A RIESGO")
    merge(2, 5, 8)
    celda(2, 5, "SERVICIOS")
    celda(2, 10, "Cobertura A:")
    celda(2, 11, cap_bas)
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
    celda(3, 11, cap_com)
    # Fila 4: datos principales + Cobertura C
    celda(4, 0, float(coef_uso))
    ws.cell(row=row0 + 4, column=col0).number_format = _PERC_FORMAT
    celda(4, 1, cap_total)
    celda(4, 2, cap_bas)
    celda(4, 3, cap_com)
    celda(4, 4, cap_vip)
    celda(4, 5, ser_total)
    celda(4, 6, ser_bas)
    celda(4, 7, ser_com)
    celda(4, 8, ser_vip)
    celda(4, 10, "Cobertura C:")
    celda(4, 11, cap_vip)
    # Fila 5: TOTAL A PAGAR / ALICUOTAS / RAMAS
    merge(5, 1, 4)
    celda(5, 1, "ALICUOTAS CORRESPONDIENTES")
    merge(5, 5, 8)
    celda(5, 5, f"TOTAL A PAGAR POR AUTOS - {periodo_nombre}".upper())
    celda(5, 10, "RAMAS VARIAS:")
    # Fila 6: coeficiente + encabezados + Rama 87
    celda(6, 0, float(coef_indice))
    ws.cell(row=row0 + 6, column=col0).number_format = _PERC_FORMAT
    celda(6, 2, "Básica")
    celda(6, 3, "Completa")
    celda(6, 4, "VIP")
    celda(6, 10, "Rama 87:")
    celda(6, 11, rama_87)
    # Fila 7: valores + total + Rama 89
    celda(7, 2, float(valor_bas))
    celda(7, 3, float(valor_com))
    celda(7, 4, float(valor_vip))
    merge(7, 5, 8)
    celda(7, 5, float(total))
    celda(7, 10, "Rama 89:")
    celda(7, 11, rama_89)
    # Fila 8: subtotales + Rama 90
    celda(8, 2, float(valor_bas * cap_bas))
    celda(8, 3, float(valor_com * cap_com))
    celda(8, 4, float(valor_vip * cap_vip))
    celda(8, 10, "Rama 90:")
    celda(8, 11, rama_90)


def exportar_cierre(
    hojas_entrada: dict | None, sintesis: dict, periodo_nombre: str
) -> BytesIO:
    """Build the 5-sheet SOS workbook (input sheets + síntesis cuadro)."""
    wb = Workbook()
    wb.remove(wb.active)

    _reproducir_hojas(wb, hojas_entrada, periodo_nombre)

    ws_sintesis = wb.create_sheet("Síntesis")
    _escribir_cuadro(ws_sintesis, sintesis, periodo_nombre)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
