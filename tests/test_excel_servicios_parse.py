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
    categoria_desde_hoja,
    normalizar_texto,
)
from src.domain.enums import CategoriaServicio
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


def test_normalizar_texto_grado_signo_formato_viejo():
    # El formato viejo usa "°" (grado) en "N°Servicio", no el ordinal "º".
    assert normalizar_texto("N°Servicio") == "n servicio"
    assert normalizar_texto("Número de Productor") == "numero de productor"


# --- categoria_desde_hoja ------------------------------------------------------


def test_categoria_desde_hoja_prefijo():
    assert categoria_desde_hoja("659 Básico") is CategoriaServicio.BASICO
    assert categoria_desde_hoja("660 Completo") is CategoriaServicio.COMPLETO
    assert categoria_desde_hoja("658 Vip") is CategoriaServicio.VIP
    assert categoria_desde_hoja("87") is CategoriaServicio.RAMA_87
    assert categoria_desde_hoja("Síntesis") is None
    assert categoria_desde_hoja("") is None


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


# --- formato viejo (2014-2018): "Producto" como código + "Número de Productor" ---


_HEADER_VIEJO = ["N°Servicio", "Fecha", "Dominio", "Producto", "Número de Productor"]


def test_leer_formato_viejo_columna_producto():
    buf = _build_xlsx(
        [
            [["fecha"], [date(2014, 7, 2)], [date(2014, 7, 30)]],
            [
                _HEADER_VIEJO,
                ["20140702200913", "02/07/2014", "SVC 636", "61", "0"],
                ["20140702900111", "02/07/2014", "ABC123", "659", "1978"],
            ],
            [_HEADER_VIEJO, ["20140703900222", "03/07/2014", "XYZ 789", "660", "8"]],
            [_HEADER_VIEJO],
            [["Síntesis"]],
        ]
    )
    filas = ImportadorServiciosExcel().leer(buf)
    assert len(filas) == 3
    assert filas[0].nro_servicio == "20140702200913"
    assert filas[0].codigo_radio == "61"  # "Producto" se mapea a codigo_radio
    assert filas[0].cod_productor == 0
    assert filas[1].codigo_radio == "659"
    assert filas[1].cod_productor == 1978
    assert filas[2].codigo_radio == "660"
    assert filas[2].cod_productor == 8


# --- leer_hojas (captura verbatim de las 4 hojas de datos) ---------------------


def test_leer_hojas_captura_4_hojas():
    buf = _workbook(
        [date(2024, 10, 1)],
        [[["S001", "15/10/2024", "ABC123", "659", "7"]]],
    )
    hojas = ImportadorServiciosExcel().leer_hojas(buf)
    assert len(hojas["hojas"]) == 4
    # hoja 0 (mes) con su fecha
    mes = hojas["hojas"][0]
    assert mes["encabezados"] == ["fecha"]
    assert mes["filas"] == [["2024-10-01"]]
    # hoja 1 (659 Básico) con encabezados + fila verbatim
    data = hojas["hojas"][1]
    assert data["encabezados"] == [
        "Nº Servicio", "Fecha", "Patente", "Código Radio", "Productor",
    ]
    assert data["filas"] == [["S001", "15/10/2024", "ABC123", "659", "7"]]
    # hojas 2 y 3 vacías (solo encabezados)
    assert hojas["hojas"][2]["filas"] == []
    assert hojas["hojas"][3]["filas"] == []
    # la hoja 4 (Síntesis) no se captura
    assert all(h["nombre"] != "Síntesis" for h in hojas["hojas"])
