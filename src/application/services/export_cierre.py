"""Pure SOS workbook export for a cierre snapshot (no DB).

Rebuilds the 5-sheet SOS layout from the normalized cierre snapshot: the month
sheet holds ``servicios_total``, the three tipo sheets hold their subsets, and
the ``Síntesis`` sheet holds the summary cuadro as key/value pairs. Fully
testable without a database.
"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

_HEADERS = ["Servicio", "Fecha", "Patente", "Código Radio", "Productor"]

_TIPO_SHEETS = (
    ("659 Básico", "servicios_basico"),
    ("660 Completo", "servicios_completo"),
    ("658 Vip", "servicios_vip"),
)


def _append_servicios(ws, rows: list[dict]) -> None:
    for s in rows:
        ws.append(
            [
                s.get("nro_servicio"),
                s.get("fecha"),
                s.get("dominio"),
                s.get("codigo_radio"),
                s.get("cod_productor"),
            ]
        )


def exportar_cierre(snapshot: dict, periodo_nombre: str) -> BytesIO:
    """Build a 5-sheet SOS workbook from a cierre ``snapshot``."""
    wb = Workbook()
    wb.remove(wb.active)

    ws_total = wb.create_sheet(periodo_nombre[:31])
    ws_total.append(_HEADERS)
    _append_servicios(ws_total, snapshot.get("servicios_total", []))

    for sheet_name, key in _TIPO_SHEETS:
        ws = wb.create_sheet(sheet_name)
        ws.append(_HEADERS)
        _append_servicios(ws, snapshot.get(key, []))

    ws_sintesis = wb.create_sheet("Síntesis")
    sint = snapshot.get("sintesis", {})
    capitas = sint.get("capitas", {})
    servicios = sint.get("servicios", {})
    valores = sint.get("valores", {})
    ws_sintesis.append(["Campo", "Valor"])
    ws_sintesis.append(["Nombre", sint.get("nombre")])
    ws_sintesis.append(["Aumento (%)", sint.get("aumento")])
    ws_sintesis.append(["Cápitas Total", capitas.get("total")])
    ws_sintesis.append(["Cápitas Básico", capitas.get("basico")])
    ws_sintesis.append(["Cápitas Completo", capitas.get("completo")])
    ws_sintesis.append(["Cápitas VIP", capitas.get("vip")])
    ws_sintesis.append(["Cápitas Rama 87", capitas.get("rama_87")])
    ws_sintesis.append(["Cápitas Rama 89", capitas.get("rama_89")])
    ws_sintesis.append(["Cápitas Rama 90", capitas.get("rama_90")])
    ws_sintesis.append(["Servicios Total", servicios.get("total")])
    ws_sintesis.append(["Servicios Básico", servicios.get("basico")])
    ws_sintesis.append(["Servicios Completo", servicios.get("completo")])
    ws_sintesis.append(["Servicios VIP", servicios.get("vip")])
    ws_sintesis.append(["Coef. Uso", sint.get("coef_uso")])
    ws_sintesis.append(["Coef. Índice", sint.get("coef_indice")])
    ws_sintesis.append(["Valor Básico", valores.get("basico")])
    ws_sintesis.append(["Valor Completo", valores.get("completo")])
    ws_sintesis.append(["Valor VIP", valores.get("vip")])
    ws_sintesis.append(["Total a pagar", sint.get("total_a_pagar")])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
