"""Pestaña Reportes: KPIs, serie mensual y tablas agregadas de servicios.

Carga todo de una sola vez vía el use case ``resumen_reportes`` dentro de UN
``PostgresUoW``; el filtro de año solo re-renderiza tabla y chart en cliente,
recalculando desde las mismas filas (sin re-query).
"""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import reportes as reportes_uc
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.formatos import format_int

# Orden de categorías (coincide conceptualmente con periodo_detalle). Se define
# localmente para no acoplar la vista al módulo de detalle.
_CATEGORIAS = ("basico", "completo", "vip", "rama_87", "rama_89", "rama_90")

# Se suman las tres ramas en una sola columna "Ramas" para no saturar la tabla
# (ocho columnas de categoría + total serían poco legibles); el detalle por rama
# sigue disponible en el agregado por categoria del use case.
_COLUMNAS_PERIODO = [
    {"name": "periodo", "label": "Periodo", "field": "periodo"},
    {"name": "basico", "label": "Básico", "field": "basico"},
    {"name": "completo", "label": "Completo", "field": "completo"},
    {"name": "vip", "label": "VIP", "field": "vip"},
    {"name": "ramas", "label": "Ramas", "field": "ramas"},
    {"name": "total", "label": "Total", "field": "total"},
]

_COLUMNAS_PRODUCTOR = [
    {"name": "productor", "label": "Productor", "field": "productor"},
    {"name": "servicios", "label": "Servicios", "field": "servicios"},
    {"name": "pct", "label": "% total", "field": "pct"},
]


def _filas_por_periodo(conteos) -> list[dict]:
    """Pivota (anio, mes, categoria, total) a una fila por periodo."""
    por_periodo: dict[tuple[int, int], dict[str, int]] = {}
    for c in conteos:
        clave = (c.anio, c.mes)
        cubo = por_periodo.setdefault(clave, dict.fromkeys(_CATEGORIAS, 0))
        cubo[c.categoria.value] += c.total

    filas: list[dict] = []
    for anio, mes in sorted(por_periodo, reverse=True):
        cubo = por_periodo[(anio, mes)]
        ramas = cubo["rama_87"] + cubo["rama_89"] + cubo["rama_90"]
        total = sum(cubo.values())
        filas.append(
            {
                "periodo": f"{anio}-{mes:02d}",
                "basico": format_int(cubo["basico"]),
                "completo": format_int(cubo["completo"]),
                "vip": format_int(cubo["vip"]),
                "ramas": format_int(ramas),
                "total": format_int(total),
            }
        )
    return filas


def _filas_productores(productores, total_servicios) -> list[dict]:
    filas = []
    for p in productores:
        pct = (p.total / total_servicios * 100) if total_servicios else 0.0
        filas.append(
            {
                "productor": p.cod_productor,
                "servicios": format_int(p.total),
                "pct": f"{pct:.1f}%",
            }
        )
    return filas


def _opciones_chart(conteos) -> dict:
    """Series de totales mensuales (últimos 24 meses) para ui.echart."""
    por_periodo: dict[tuple[int, int], int] = {}
    for c in conteos:
        clave = (c.anio, c.mes)
        por_periodo[clave] = por_periodo.get(clave, 0) + c.total

    fechas = sorted(por_periodo)[-24:]
    etiquetas = [f"{a}-{m:02d}" for a, m in fechas]
    valores = [por_periodo[k] for k in fechas]
    return {
        "textStyle": {"color": "#9CA3AF"},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": etiquetas,
            "axisLabel": {"color": "#9CA3AF"},
            "axisLine": {"lineStyle": {"color": "#6B7280"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#9CA3AF"},
            "splitLine": {"lineStyle": {"color": "#374151"}},
        },
        "series": [
            {
                "type": "bar",
                "data": valores,
                "itemStyle": {"color": "#DC2626"},
                "barMaxWidth": 36,
            }
        ],
    }


def _kpi(label: str, valor: str) -> None:
    with ui.card().classes("flex-1 min-w-[160px]"):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(valor).classes("text-h4")


async def _load():
    async with PostgresUoW() as uow:
        return await reportes_uc.resumen_reportes(uow)


async def render(_user: dict) -> None:
    resumen = await _load()
    conteos = resumen.conteos_categoria

    with ui.column().classes("w-full gap-4"):
        ui.label("Reportes").classes("text-h5")

        with ui.row().classes("w-full gap-4"):
            _kpi("Total servicios", format_int(resumen.total_servicios))
            _kpi("Periodos con servicios", format_int(resumen.periodos_con_servicios))
            _kpi("Productores distintos", format_int(resumen.productores_distintos))
            _kpi("Tipos de servicio", format_int(resumen.tipos_distintos))

        anios = sorted({c.anio for c in conteos}, reverse=True)
        opciones_anio = {"Todos": None} | {str(a): a for a in anios}
        selector_anio = ui.select(opciones_anio, value=None, label="Año").props(
            "clearable"
        )

        ui.label("Servicios por periodo").classes("text-h6")
        tabla_periodos = ui.table(
            rows=_filas_por_periodo(conteos),
            columns=_COLUMNAS_PERIODO,
            pagination=10,
        ).classes("w-full")

        ui.label("Evolución mensual (últimos 24 meses)").classes("text-h6")
        chart = ui.echart(_opciones_chart(conteos)).classes("w-full h-72")

        ui.label("Top productores").classes("text-h6")
        ui.table(
            rows=_filas_productores(resumen.top_productores, resumen.total_servicios),
            columns=_COLUMNAS_PRODUCTOR,
            pagination=10,
        ).classes("w-full")

        def _aplicar_filtro() -> None:
            anio = selector_anio.value
            filtrados = [c for c in conteos if anio is None or c.anio == anio]
            tabla_periodos.update_rows(_filas_por_periodo(filtrados))
            chart.run_chart_method("setOption", _opciones_chart(filtrados))

        selector_anio.on("update:model-value", _aplicar_filtro)
