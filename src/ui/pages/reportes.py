"""Pestaña Reportes: dashboard con gráficos por tipo y periodo.

Carga todo de una sola vez vía el use case ``resumen_dashboard`` dentro de UN
``PostgresUoW``: servicios por tipo, servicios por periodo, y la serie de
periodos con su ``cuadro`` de cierre (aumento, capitas, coeficientes, valores y
total). Los gráficos se construyen en cliente sin re-query.
"""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import reportes as reportes_uc
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui import theme
from src.ui.formatos import format_ars, format_int

# Orden canónico de categorías para cápitas apiladas y valores.
_CATEGORIAS_CAPITAS = ("basico", "completo", "vip", "rama_87", "rama_89", "rama_90")
_CATEGORIAS_AUTOMOTOR = ("basico", "completo", "vip")

_LABEL = {
    "basico": "Básico",
    "completo": "Completo",
    "vip": "VIP",
    "rama_87": "Rama 87",
    "rama_89": "Rama 89",
    "rama_90": "Rama 90",
}

_MESES_SERIE = 24


def _to_float(value) -> float | None:
    """Convierte un valor de snapshot (str 2dp o numérico) a float, o None."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _servicios_por_periodo(conteos) -> list[tuple[tuple[int, int], int]]:
    """Suma los conteos por (anio, mes) y los devuelve ordenados asc."""
    por_periodo: dict[tuple[int, int], int] = {}
    for c in conteos:
        clave = (c.anio, c.mes)
        por_periodo[clave] = por_periodo.get(clave, 0) + c.total
    return sorted(por_periodo.items())


def _periodo_con_mas_servicios(conteos) -> tuple[str, int]:
    """Devuelve (etiqueta, total) del periodo con más servicios."""
    por_periodo = _servicios_por_periodo(conteos)
    if not por_periodo:
        return "—", 0
    (anio, mes), total = max(
        por_periodo, key=lambda kv: (kv[1], kv[0][0], kv[0][1])
    )
    return f"{anio}-{mes:02d}", total


def _cuadros(periodos):
    """Periodos cerrados con cuadro, ordenados asc por (anio, mes)."""
    cerrados = [p for p in periodos if p.cerrado and p.cuadro is not None]
    cerrados.sort(key=lambda p: (p.anio, p.mes))
    return cerrados


def _opciones_servicios_por_tipo(conteos_tipo) -> dict:
    """Bar chart: cantidad de servicios por tipo de servicio."""
    categorias: list[str] = []
    data: list[dict] = []
    for c in conteos_tipo:
        color = theme.CATEGORIA_COLORS.get(c.categoria.value, "#DC2626")
        categorias.append(f"{c.nombre} {c.codigo}")
        data.append({"value": c.total, "itemStyle": {"color": color}})
    return {
        "textStyle": {"color": "#9CA3AF"},
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": categorias,
            "axisLabel": {"color": "#9CA3AF"},
            "axisLine": {"lineStyle": {"color": "#6B7280"}},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#9CA3AF"},
            "splitLine": {"lineStyle": {"color": "#374151"}},
        },
        "series": [{"type": "bar", "data": data, "barMaxWidth": 48}],
    }


def _opciones_servicios_periodo(conteos) -> dict:
    """Line chart: evolución mensual de servicios (últimos N meses)."""
    puntos = _servicios_por_periodo(conteos)[-_MESES_SERIE:]
    etiquetas = [f"{a}-{m:02d}" for (a, m), _ in puntos]
    valores = [v for _, v in puntos]
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
                "type": "line",
                "data": valores,
                "itemStyle": {"color": "#DC2626"},
                "lineStyle": {"color": "#DC2626"},
                "smooth": True,
                "symbolSize": 6,
            }
        ],
    }


def _opciones_valor_aumento(cuadros, tipo: str) -> dict:
    """Dual axis: valor de alícuota (línea, izq) + aumento % (barras, der)."""
    etiquetas = [c.nombre for c in cuadros]
    valores: list[float | None] = []
    aumentos: list[float] = []
    for c in cuadros:
        valores_map = c.cuadro.get("valores") or {}
        valores.append(_to_float(valores_map.get(tipo)))
        aumentos.append(_to_float(c.cuadro.get("aumento")) or 0.0)
    return {
        "textStyle": {"color": "#9CA3AF"},
        "tooltip": {"trigger": "axis"},
        "legend": {
            "data": ["Valor alícuota", "Aumento %"],
            "textStyle": {"color": "#9CA3AF"},
        },
        "grid": {"left": "3%", "right": "4%", "bottom": "3%", "containLabel": True},
        "xAxis": {
            "type": "category",
            "data": etiquetas,
            "axisLabel": {"color": "#9CA3AF"},
            "axisLine": {"lineStyle": {"color": "#6B7280"}},
        },
        "yAxis": [
            {
                "type": "value",
                "name": "Valor ($)",
                "nameTextStyle": {"color": "#9CA3AF"},
                "axisLabel": {"color": "#9CA3AF"},
                "splitLine": {"lineStyle": {"color": "#374151"}},
            },
            {
                "type": "value",
                "name": "Aumento %",
                "nameTextStyle": {"color": "#9CA3AF"},
                "axisLabel": {"color": "#9CA3AF"},
                "splitLine": {"show": False},
            },
        ],
        "series": [
            {
                "name": "Valor alícuota",
                "type": "line",
                "data": valores,
                "yAxisIndex": 0,
                "itemStyle": {"color": "#F59E0B"},
                "lineStyle": {"color": "#F59E0B"},
                "smooth": True,
                "symbolSize": 6,
            },
            {
                "name": "Aumento %",
                "type": "bar",
                "data": aumentos,
                "yAxisIndex": 1,
                "itemStyle": {"color": "#DC2626"},
                "barMaxWidth": 24,
            },
        ],
    }


def _opciones_capitas(cuadros) -> dict:
    """Stacked bar: cápitas por categoría por periodo."""
    etiquetas = [c.nombre for c in cuadros]
    series: list[dict] = []
    for cat in _CATEGORIAS_CAPITAS:
        data: list[int] = []
        for c in cuadros:
            capitas_map = c.cuadro.get("capitas") or {}
            data.append(capitas_map.get(cat, 0))
        series.append(
            {
                "name": _LABEL[cat],
                "type": "bar",
                "stack": "total",
                "data": data,
                "itemStyle": {"color": theme.CATEGORIA_COLORS.get(cat, "#DC2626")},
            }
        )
    return {
        "textStyle": {"color": "#9CA3AF"},
        "tooltip": {"trigger": "axis"},
        "legend": {
            "data": [_LABEL[c] for c in _CATEGORIAS_CAPITAS],
            "textStyle": {"color": "#9CA3AF"},
        },
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
        "series": series,
    }


def _opciones_coeficientes(cuadros) -> dict:
    """Line chart: coef_uso y coef_indice por periodo."""
    etiquetas = [c.nombre for c in cuadros]
    coef_uso = [_to_float(c.cuadro.get("coef_uso")) for c in cuadros]
    coef_indice = [_to_float(c.cuadro.get("coef_indice")) for c in cuadros]
    return {
        "textStyle": {"color": "#9CA3AF"},
        "tooltip": {"trigger": "axis"},
        "legend": {
            "data": ["coef_uso", "coef_indice"],
            "textStyle": {"color": "#9CA3AF"},
        },
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
                "name": "coef_uso",
                "type": "line",
                "data": coef_uso,
                "itemStyle": {"color": "#DC2626"},
                "lineStyle": {"color": "#DC2626"},
                "smooth": True,
                "symbolSize": 6,
            },
            {
                "name": "coef_indice",
                "type": "line",
                "data": coef_indice,
                "itemStyle": {"color": "#9CA3AF"},
                "lineStyle": {"color": "#9CA3AF", "type": "dashed"},
                "symbolSize": 6,
            },
        ],
    }


def _kpi(label: str, valor: str) -> None:
    with ui.card().classes("flex-1 min-w-[150px]"):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(valor).classes("text-h5")


async def _load():
    async with PostgresUoW() as uow:
        return await reportes_uc.resumen_dashboard(uow)


async def render(_user: dict) -> None:
    resumen = await _load()
    cuadros = _cuadros(resumen.periodos)[-_MESES_SERIE:]
    periodo_mas, total_mas = _periodo_con_mas_servicios(resumen.conteos_categoria)

    # KPI: coef de uso y total a pagar del último cierre oficial.
    coef_uso = "—"
    total_pagar = "—"
    if cuadros:
        ultimo = cuadros[-1].cuadro
        coef = _to_float(ultimo.get("coef_uso"))
        coef_uso = f"{coef:.4f}" if coef is not None else "—"
        total_pagar = format_ars(_to_float(ultimo.get("total_a_pagar")))

    with ui.column().classes("w-full gap-4"):
        ui.label("Reportes").classes("text-h5")

        with ui.row().classes("w-full gap-3"):
            _kpi("Total servicios", format_int(resumen.total_servicios))
            _kpi("Periodo con más servicios", f"{periodo_mas} ({format_int(total_mas)})")
            _kpi("Tipos de servicio", format_int(resumen.tipos_distintos))
            _kpi("Coef. uso último cierre", coef_uso)
            _kpi("Total a pagar último cierre", total_pagar)

        with ui.grid(columns=2).classes("w-full gap-4"):
            with ui.card().classes("w-full"):
                ui.label("Servicios por tipo de servicio").classes("text-h6")
                ui.echart(_opciones_servicios_por_tipo(resumen.conteos_tipo)).classes(
                    "w-full h-72"
                )

            with ui.card().classes("w-full"):
                ui.label("Servicios por periodo").classes("text-h6")
                ui.echart(
                    _opciones_servicios_periodo(resumen.conteos_categoria)
                ).classes("w-full h-72")

            with ui.card().classes("w-full").style("grid-column: span 2"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Valor de alícuota + aumento aplicado").classes("text-h6")
                    selector_tipo = ui.select(
                        {t: _LABEL[t] for t in _CATEGORIAS_AUTOMOTOR},
                        value="basico",
                        label="Tipo de servicio",
                    ).props("dense")
                chart_valor = ui.echart(
                    _opciones_valor_aumento(cuadros, "basico")
                ).classes("w-full h-80")

            with ui.card().classes("w-full"):
                ui.label("Cápitas por tipo de servicio").classes("text-h6")
                ui.echart(_opciones_capitas(cuadros)).classes("w-full h-72")

            with ui.card().classes("w-full"):
                ui.label("Coeficiente de uso").classes("text-h6")
                ui.echart(_opciones_coeficientes(cuadros)).classes("w-full h-72")

        def _cambiar_tipo() -> None:
            chart_valor.run_chart_method(
                "setOption", _opciones_valor_aumento(cuadros, selector_tipo.value)
            )

        selector_tipo.on("update:model-value", _cambiar_tipo)
