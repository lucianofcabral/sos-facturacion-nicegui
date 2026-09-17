"""Tests for the cierre Excel export (pure service + use case)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from openpyxl import load_workbook

from conftest import run_test
from src.application.services.export_cierre import exportar_cierre
from src.application.use_cases import cierre, periodo
from src.domain.dto.create import CreatePeriodo
from src.domain.enums import EstadoCierre, OrigenCierre
from src.domain.exceptions import PeriodoNotClosedError
from src.domain.models.entities import Cierre
from src.infrastructure.adapters.uow import PostgresUoW


def _sintesis() -> dict:
    return {
        "nombre": "OCTUBRE 2025",
        "aumento": "6.02",
        "capitas": {
            "total": 70027, "basico": 6472, "completo": 21747, "vip": 41808,
            "rama_87": 1143, "rama_89": 3540, "rama_90": 129,
        },
        "servicios": {"total": 1040, "basico": 62, "completo": 367, "vip": 611},
        "coef_uso": "0.01",
        "coef_indice": "0.03",
        "valores": {"basico": "1463.61", "completo": "1777.71", "vip": "1920.29"},
        "total_a_pagar": "129116255.39",
    }


def _hojas_entrada() -> dict:
    headers = ["Servicio", "Fecha", "Patente", "Codigo Radio", "Productor"]
    return {
        "hojas": [
            {
                "nombre": "Octubre",
                "encabezados": headers,
                "filas": [
                    ["S1", "01/10/2025", "ABC123", 659, 1],
                    ["S2", "02/10/2025", "XYZ789", 658, 2],
                ],
            },
            {
                "nombre": "659 Básico",
                "encabezados": headers,
                "filas": [["S1", "01/10/2025", "ABC123", 659, 1]],
            },
            {"nombre": "660 Completo", "encabezados": headers, "filas": []},
            {
                "nombre": "658 Vip",
                "encabezados": headers,
                "filas": [["S2", "02/10/2025", "XYZ789", 658, 2]],
            },
        ]
    }


def test_exportar_cierre_cinco_hojas():
    buf = exportar_cierre(_hojas_entrada(), _sintesis(), "OCTUBRE 2025")
    wb = load_workbook(buf)
    assert wb.sheetnames == [
        "Octubre", "659 Básico", "660 Completo", "658 Vip", "Síntesis",
    ]
    # hoja total tiene header + 2 filas
    ws_total = wb["Octubre"]
    assert ws_total.max_row == 3
    assert ws_total.cell(row=1, column=1).value == "Servicio"
    # hoja básico tiene 2 filas (header + 1)
    assert wb["659 Básico"].max_row == 2
    # hoja completo vacía (solo header)
    assert wb["660 Completo"].max_row == 1
    # síntesis: Cobertura A = cápitas básicas (no el total)
    ws_sint = wb["Síntesis"]
    assert ws_sint.cell(row=4, column=15).value == "Cobertura A:"  # O4
    assert ws_sint.cell(row=4, column=16).value == 6472  # P4 = básicas
    assert ws_sint.cell(row=5, column=16).value == 21747  # P5 = completa
    assert ws_sint.cell(row=6, column=16).value == 41808  # P6 = vip


def test_exportar_cierre_sin_hojas_entrada():
    buf = exportar_cierre(None, _sintesis(), "VACIO")
    wb = load_workbook(buf)
    assert wb.sheetnames == [
        "VACIO", "659 Básico", "660 Completo", "658 Vip", "Síntesis",
    ]
    assert wb["VACIO"].max_row == 1  # solo header (fallback)


def test_exportar_cierre_formato_legacy():
    buf = exportar_cierre(_hojas_entrada(), _sintesis(), "OCTUBRE 2025")
    wb = load_workbook(buf)
    ws = wb["Síntesis"]
    # conteos con separador de miles
    assert ws["P4"].number_format == "#,###,##0"
    assert ws["F6"].number_format == "#,###,##0"
    # coeficientes en porcentaje
    assert ws["E6"].number_format == "0.00%"
    assert ws["E8"].number_format == "0.00%"
    # dinero con signo peso
    assert ws["G9"].number_format == "$ #,###,##0.00"
    assert ws["J9"].number_format == "$ #,###,##0.00"
    # negrita en total a pagar y subtotales
    assert ws["J9"].font.bold is True
    assert ws["G10"].font.bold is True
    assert ws["O2"].font.bold is True
    # ancho de columnas E..P
    assert ws.column_dimensions["E"].width == 19
    # bordes finos del cuadro (grilla legacy)
    assert ws["E2"].border.left.style == "thin"
    assert ws["E2"].border.top.style == "thin"
    assert ws["M2"].border.right.style == "thin"
    assert ws["F4"].border.right.style == "thin"
    assert ws["E10"].border.bottom.style == "thin"
    assert ws["J7"].border.right.style == "thin"


def test_exportar_cierre_con_previos():
    previos = [
        {**_sintesis(), "nombre": "JUNIO 2025"},
        {**_sintesis(), "nombre": "MAYO 2025"},
    ]
    buf = exportar_cierre(
        _hojas_entrada(), _sintesis(), "JULIO 2025", previos=previos
    )
    wb = load_workbook(buf)
    ws = wb["Síntesis"]
    # actual en E4; previos apilados con stride 10 (E14, E24)
    assert ws.cell(row=4, column=5).value == "JULIO 2025"
    assert ws.cell(row=14, column=5).value == "JUNIO 2025"
    assert ws.cell(row=24, column=5).value == "MAYO 2025"
    # fila separadora en blanco entre bloques
    assert ws.cell(row=11, column=5).value is None
    assert ws.cell(row=21, column=5).value is None
    # cada bloque repite la cobertura A (básicas)
    assert ws.cell(row=4, column=16).value == 6472
    assert ws.cell(row=14, column=16).value == 6472


def test_descargar_cierre_excel_sin_cierre():
    async def main():
        async with PostgresUoW() as uow:
            p = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Ene", anio=2026, mes=1)
            )
            with pytest.raises(PeriodoNotClosedError):
                await cierre.descargar_cierre_excel(uow, p.id)

    run_test(main)


def test_descargar_cierre_excel_devuelve_bytes_xlsx():
    async def main():
        async with PostgresUoW() as uow:
            p = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Ene", anio=2026, mes=1)
            )
            await uow.cierres.add(
                Cierre(
                    periodo_id=p.id,
                    version=1,
                    estado=EstadoCierre.OFICIAL,
                    origen=OrigenCierre.MANUAL,
                    aumento=Decimal("0"),
                    snapshot=_sintesis(),
                )
            )
            await uow.commit()
            content = await cierre.descargar_cierre_excel(uow, p.id)
            assert content.startswith(b"PK")  # xlsx es un zip
            wb = load_workbook(__import__("io").BytesIO(content))
            assert wb.sheetnames == [
                "Ene", "659 Básico", "660 Completo", "658 Vip", "Síntesis",
            ]

    run_test(main)


def test_descargar_cierre_excel_incluye_previos():
    async def main():
        async with PostgresUoW() as uow:
            prev = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Dic", anio=2025, mes=12)
            )
            await uow.cierres.add(
                Cierre(
                    periodo_id=prev.id,
                    version=1,
                    estado=EstadoCierre.OFICIAL,
                    origen=OrigenCierre.MANUAL,
                    aumento=Decimal("0"),
                    snapshot={**_sintesis(), "nombre": "Dic"},
                )
            )
            target = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Ene", anio=2026, mes=1)
            )
            await uow.cierres.add(
                Cierre(
                    periodo_id=target.id,
                    version=1,
                    estado=EstadoCierre.OFICIAL,
                    origen=OrigenCierre.MANUAL,
                    aumento=Decimal("0"),
                    snapshot=_sintesis(),
                )
            )
            await uow.commit()
            content = await cierre.descargar_cierre_excel(uow, target.id)
            wb = load_workbook(__import__("io").BytesIO(content))
            ws = wb["Síntesis"]
            # actual en E4, previo en E14 (stride 10)
            assert ws.cell(row=4, column=5).value == "Ene"
            assert ws.cell(row=14, column=5).value == "Dic"

    run_test(main)
