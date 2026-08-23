"""Unit tests for the pure Excel service parser (no DB).

Covers text normalization, fuzzy column mapping, dayfirst date parsing, int
coercion, single-month validation, wrong sheet count, and missing columns.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook

from src.application.services.excel_servicios import (
    FilaServicio,
    ImportadorServiciosExcel,
    normalizar_texto,
)
from src.domain.exceptions import ImportServiciosError


def _build_xlsx(sheets: list[list[list]]) -> BytesIO:
    """Build an in-memory workbook with one sheet per element of ``sheets``."""
    wb = Workbook()
    wb.remove(wb.active)
    for rows in sheets:
        ws = wb.create_sheet()
        for row in rows:
            ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


_HEADER = ["Nº Servicio", "Fecha", "Patente", "Código Radio", "Productor"]


def _data_row(nro, fecha, patente, codigo, productor):
    return [nro, fecha, patente, codigo, productor]


def _workbook(mes_fechas: list, data_sheets: list[list[list]]) -> BytesIO:
    """Build a 5-sheet workbook: sheet 0 (mes), sheets 1-3 (data), sheet 4."""
    sheets: list[list[list]] = [[["fecha"]] + [[f] for f in mes_fechas]]
    for i in range(3):
        rows = data_sheets[i] if i < len(data_sheets) else []
        sheets.append([_HEADER, *rows])
    sheets.append([["Síntesis"], ["resumen"]])
    return _build_xlsx(sheets)


def _leer(mes_fechas: list, data_sheets: list[list[list]]) -> list[FilaServicio]:
    return ImportadorServiciosExcel().leer(_workbook(mes_fechas, data_sheets))


# --- normalizar_texto ----------------------------------------------------------


def test_normalizar_texto_tildes_espacios_numero():
    assert normalizar_texto("  Nº  Servicio ") == "no servicio"
    assert normalizar_texto("CÓDIGO  RADIO") == "codigo radio"
    assert normalizar_texto("Patente\tDoble") == "patente doble"
    assert normalizar_texto("Productor") == "productor"


# --- happy path + normalization ------------------------------------------------


def test_leer_happy_path_normaliza_columnas():
    filas = _leer(
        [date(2024, 10, 1), date(2024, 10, 31)],
        [
            [
                _data_row("  S001 ", "15/10/2024", "abc-123", "659.0", "7"),
                _data_row("S002", date(2024, 10, 16), "XYZ 789", 660, 8),
            ],
            [_data_row("S003", "20/10/2024", "AAA111", "87", "9")],
            [],
        ],
    )
    assert len(filas) == 3
    assert filas[0].nro_servicio == "s001"  # strip/lower
    assert filas[0].fecha == date(2024, 10, 15)  # dayfirst
    assert filas[0].dominio == "ABC123"  # upper + sanitize
    assert filas[0].codigo_radio == "659"  # int-coerced then str
    assert filas[0].cod_productor == 7
    assert filas[1].fecha == date(2024, 10, 16)  # date cell
    assert filas[1].codigo_radio == "660"
    assert filas[1].cod_productor == 8
    assert filas[1].dominio == "XYZ 789"
    assert filas[2].codigo_radio == "87"
    assert filas[2].cod_productor == 9


# --- single-month validation ---------------------------------------------------


def test_mes_unico_ok():
    filas = _leer(
        [date(2024, 10, 1), date(2024, 10, 15), date(2024, 10, 31)],
        [[_data_row("S001", "01/10/2024", "ABC123", "659", "7")]],
    )
    assert len(filas) == 1


def test_mes_mixto_error():
    with pytest.raises(ImportServiciosError):
        _leer(
            [date(2024, 10, 1), date(2024, 11, 1)],
            [[_data_row("S001", "01/10/2024", "ABC123", "659", "7")]],
        )


# --- structural errors ---------------------------------------------------------


def test_numero_hojas_distinto_error():
    buf = _build_xlsx([[["fecha"]], [_HEADER], [["Síntesis"]]])  # 3 sheets
    with pytest.raises(ImportServiciosError):
        ImportadorServiciosExcel().leer(buf)


def test_columna_faltante_error():
    buf = _build_xlsx(
        [
            [["fecha"], [date(2024, 10, 1)]],
            [["Nº Servicio", "Fecha", "Patente", "Código Radio"],  # sin Productor
             ["S001", "01/10/2024", "ABC123", "659"]],
            [_HEADER],
            [_HEADER],
            [["Síntesis"]],
        ]
    )
    with pytest.raises(ImportServiciosError):
        ImportadorServiciosExcel().leer(buf)


def test_codigo_radio_vacio_error():
    buf = _build_xlsx(
        [
            [["fecha"], [date(2024, 10, 1)]],
            [_HEADER, ["S001", "01/10/2024", "ABC123", "", "7"]],
            [_HEADER],
            [_HEADER],
            [["Síntesis"]],
        ]
    )
    with pytest.raises(ImportServiciosError):
        ImportadorServiciosExcel().leer(buf)
