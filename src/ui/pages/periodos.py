"""Vista de periodos en cards paginadas.

Los periodos se listan en orden descendente por (anio, mes) con su estado de
cierre. El click en una card navega al detalle del periodo. Las cards de
periodos cerrados muestran el cuadro de síntesis oficial completo (cápitas por
categoría y ramas, servicios, coeficientes, valores y total a pagar); los
abiertos no muestran cuadro.
"""

from __future__ import annotations

import math

from nicegui import ui

from src.application.use_cases import periodo as periodo_uc
from src.domain.dto.create import CreatePeriodo
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog
from src.ui.dialogos.periodo import PERIODO_FIELDS
from src.ui.formatos import format_ars, format_pct
from src.ui.theme import CATEGORIA_COLORS

_PAGE_SIZE = 24


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await periodo_uc.listar_periodos_con_estado(uow)
    return [
        {
            "id": i.id,
            "nombre": i.nombre,
            "anio": i.anio,
            "mes": i.mes,
            "cerrado": i.cerrado,
            "total": i.total,
            "cuadro": i.cuadro,
        }
        for i in items
    ]


async def _crear_periodo() -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await periodo_uc.crear_periodo(
                uow,
                CreatePeriodo(
                    nombre=values["nombre"], anio=values["anio"], mes=values["mes"]
                ),
            )
        ui.navigate.reload()

    await open_form_dialog(
        title="Nuevo periodo", fields=PERIODO_FIELDS, on_submit=_submit
    )


def _stat(label: str, value: str, *, color: str | None = None) -> None:
    """Par label/valor alineado a lo ancho (celda del grid de síntesis).

    ``color`` dibuja un punto de categoría antes del label, usando la paleta
    por ``categoria`` de ``theme.CATEGORIA_COLORS``.
    """
    with ui.row().classes("w-full items-center justify-between gap-2"):
        with ui.row().classes("items-center gap-1.5 min-w-0"):
            if color:
                ui.element("span").style(
                    f"display:inline-block;width:8px;height:8px;"
                    f"border-radius:9999px;background:{color};flex-shrink:0"
                )
            ui.label(label).classes("text-caption text-grey-7")
        ui.label(value).classes("text-caption text-right")


def _fmt_entero(v) -> str:
    """Formatea un entero con separador de miles; ``—`` si no es numérico."""
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return "—"


def _seccion(titulo: str) -> None:
    """Mini-encabezado de sección dentro del cuadro de síntesis."""
    ui.separator()
    ui.label(titulo).classes(
        "text-caption font-bold uppercase tracking-wide text-grey-6"
    )


def _grid_sintesis():
    """Grilla de 2 columnas para las celdas de una sección del cuadro."""
    return ui.grid(columns="repeat(2, minmax(0, 1fr))").classes(
        "w-full gap-x-4 gap-y-1"
    )


def _render_sintesis(cuadro: dict) -> None:
    """Renderiza el cuadro oficial completo dentro de una card de periodo.

    Agrupa las cápitas en Automotores vs Ramas Varias y separa coeficientes y
    valores en secciones propias, con puntos de color por categoría.
    """
    capitas = cuadro.get("capitas") or {}
    servicios = cuadro.get("servicios") or {}
    valores = cuadro.get("valores") or {}

    ui.label("Total a pagar").classes("text-caption")
    ui.label(format_ars(cuadro.get("total_a_pagar"))).classes("text-h5 text-primary")

    with _grid_sintesis().classes("mt-1"):
        _stat("Cápitas total", _fmt_entero(capitas.get("total")))
        _stat("Servicios total", _fmt_entero(servicios.get("total")))

    with ui.grid(columns="repeat(2, minmax(0, 1fr))").classes(
        "w-full gap-x-4 items-start"
    ):
        with ui.column().classes("w-full gap-1"):
            _seccion("Automotores")
            _stat(
                "Básico",
                _fmt_entero(capitas.get("basico")),
                color=CATEGORIA_COLORS["basico"],
            )
            _stat(
                "Completo",
                _fmt_entero(capitas.get("completo")),
                color=CATEGORIA_COLORS["completo"],
            )
            _stat(
                "VIP",
                _fmt_entero(capitas.get("vip")),
                color=CATEGORIA_COLORS["vip"],
            )

        with ui.column().classes("w-full gap-1"):
            _seccion("Ramas Varias")
            _stat(
                "Rama 87",
                _fmt_entero(capitas.get("rama_87")),
                color=CATEGORIA_COLORS["rama_87"],
            )
            _stat(
                "Rama 89",
                _fmt_entero(capitas.get("rama_89")),
                color=CATEGORIA_COLORS["rama_89"],
            )
            _stat(
                "Rama 90",
                _fmt_entero(capitas.get("rama_90")),
                color=CATEGORIA_COLORS["rama_90"],
            )

    with ui.grid(columns="repeat(2, minmax(0, 1fr))").classes(
        "w-full gap-x-4 items-start"
    ):
        with ui.column().classes("w-full gap-1"):
            _seccion("Ajuste")
            _stat(
                "Aumento",
                format_pct(cuadro.get("aumento"), fraction=False),
            )
            _stat("Coef. uso", format_pct(cuadro.get("coef_uso")))
            _stat("Coef. índice", format_pct(cuadro.get("coef_indice")))

        with ui.column().classes("w-full gap-1"):
            _seccion("Valores")
            _stat(
                "Básico",
                format_ars(valores.get("basico")),
                color=CATEGORIA_COLORS["basico"],
            )
            _stat(
                "Completo",
                format_ars(valores.get("completo")),
                color=CATEGORIA_COLORS["completo"],
            )
            _stat(
                "VIP",
                format_ars(valores.get("vip")),
                color=CATEGORIA_COLORS["vip"],
            )


def _render_card(container: ui.element, p: dict) -> None:
    with (
        container,
        ui.card()
        .classes("w-full cursor-pointer hover:shadow-md")
        .on("click", lambda pid=p["id"]: ui.navigate.to(f"/periodo/{pid}")),
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(p["nombre"]).classes("text-h6")
            if p["cerrado"]:
                ui.badge("Oficial", color="green")
            else:
                ui.badge("Abierto", color="grey")
        ui.label(f"{p['anio']} / {p['mes']}").classes("text-caption text-grey-7")
        if p["cerrado"]:
            cuadro = p.get("cuadro")
            if cuadro:
                ui.separator()
                _render_sintesis(cuadro)
            elif p["total"] is not None:
                with ui.column().classes("mt-2 items-start"):
                    ui.label("Total oficial").classes("text-caption")
                    ui.label(format_ars(p["total"])).classes("text-h5 text-primary")
        else:
            ui.label("Sin cierre oficial").classes("text-caption text-grey-7 mt-1")


async def render(_user: dict) -> None:
    items = await _load()
    total_pages = max(1, math.ceil(len(items) / _PAGE_SIZE))

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Periodos").classes("text-h5")
            ui.button("Nuevo periodo", on_click=_crear_periodo)

        container = ui.grid(columns=3).classes("w-full gap-4")

        def _render_page(page: int) -> None:
            container.clear()
            start = (page - 1) * _PAGE_SIZE
            for p in items[start : start + _PAGE_SIZE]:
                _render_card(container, p)

        _render_page(1)

        if total_pages > 1:
            ui.pagination(
                1,
                total_pages,
                direction_links=True,
                on_change=lambda e: _render_page(e.value or 1),
            )
