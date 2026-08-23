"""Unit tests for the pure Panel historico parser (no DB).

Builds an in-memory workbook with the three sheets the parser reads by name
(Inicial / SintesisH / Aumentos) and asserts the typed ``DatosPanel`` result:
contiguous periodos, 108 initial alicuotas with the Inicial base values, the
síntesis month rows, and the aumentos dict (including a double-aumento month).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import Workbook

from src.application.services.panel_historico import ParserPanelHistorico
from src.domain.exceptions import PanelHistoricoError


def _build_xlsx(sheets: dict[str, list[list]]) -> BytesIO:
    """Build an in-memory workbook with the given named sheets."""
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for row in rows:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _inicial_rows() -> list[list]:
    """36 coef (0.030..0.065) x 3 prestaciones = 108 alicuotas, Inicial bases."""
    rows: list[list] = [["Indice", "idPrestacion", "corta", "larga", "Valor"]]
    bases = {1: Decimal("8.94"), 2: Decimal("10.84"), 3: Decimal("12.83")}
    coefs = [Decimal("0.030") + Decimal("0.001") * i for i in range(36)]
    for prest, base in bases.items():
        for coef in coefs:
            valor = (base * coef / Decimal("0.03")).quantize(Decimal("0.01"))
            rows.append([float(coef), prest, "corta", "larga", float(valor)])
    return rows


def _sintesis_rows() -> list[list]:
    return [
        [
            "Periodo",
            "c_basico",
            "c_completo",
            "c_vip",
            "s_basico",
            "s_completo",
            "s_vip",
            "r_87",
            "r_89",
            "r_90",
            "coef",
            "coef minimo",
        ],
        [date(2014, 7, 1), 5306, 19609, 19123, 110, 614, 370, 1550, 3482, 279, 0.02, 0.02],
        [date(2014, 8, 1), 5286, 19372, 19344, 105, 609, 389, 1576, 3578, 276, 0.02, 0.02],
        [date(2014, 9, 1), 5190, 19270, 19591, 93, 546, 361, 1537, 3509, 286, 0.02, 0.02],
    ]


def _aumentos_rows() -> list[list]:
    return [
        ["Fecha", "Aumento"],
        [date(2014, 8, 1), 0],
        [date(2014, 9, 12), 15],
        [date(2015, 2, 1), 10],
    ]


def _workbook() -> BytesIO:
    return _build_xlsx(
        {
            "Inicial": _inicial_rows(),
            "SintesisH": _sintesis_rows(),
            "Aumentos": _aumentos_rows(),
        }
    )


def test_parse_panel_historico():
    datos = ParserPanelHistorico().leer(_workbook())

    # contiguos periodos (anio, mes) from SintesisH
    assert datos.periodos == [(2014, 7), (2014, 8), (2014, 9)]

    # 108 alicuotas (36 coef x 3 prestaciones) with Inicial bases @ coef 0.03
    assert len(datos.alicuotas_iniciales) == 108
    assert datos.alicuotas_iniciales[0] == (1, Decimal("0.030"), Decimal("8.94"))
    assert (2, Decimal("0.030"), Decimal("10.84")) in datos.alicuotas_iniciales
    assert (3, Decimal("0.030"), Decimal("12.83")) in datos.alicuotas_iniciales

    # sintesis dict carries per-month capitas and service counts
    assert set(datos.sintesis.keys()) == {(2014, 7), (2014, 8), (2014, 9)}
    mes = datos.sintesis[(2014, 7)]
    assert mes.c_basico == 5306
    assert mes.s_vip == 370
    assert mes.r_89 == 3482

    # aumentos: 0 no-op row + a real row, keyed by (anio, mes)
    assert datos.aumentos[(2014, 8)] == [Decimal("0")]
    assert datos.aumentos[(2014, 9)] == [Decimal("15")]
    assert (2014, 7) not in datos.aumentos


def test_parse_aumentos_double_month():
    sheets = {
        "Inicial": _inicial_rows(),
        "SintesisH": _sintesis_rows(),
        "Aumentos": [
            ["Fecha", "Aumento"],
            [date(2022, 8, 1), 5.3],
            [date(2022, 8, 17), 7.4],
        ],
    }
    datos = ParserPanelHistorico().leer(_build_xlsx(sheets))
    assert datos.aumentos[(2022, 8)] == [Decimal("5.3"), Decimal("7.4")]


def test_parse_missing_sheet_error():
    buf = _build_xlsx({"Inicial": _inicial_rows(), "Aumentos": _aumentos_rows()})
    with pytest.raises(PanelHistoricoError):
        ParserPanelHistorico().leer(buf)
