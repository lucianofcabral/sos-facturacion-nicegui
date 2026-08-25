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


def _stat(label: str, value: str) -> None:
    """Par label/valor alineado a lo ancho (celda del grid de síntesis)."""
    with ui.row().classes("w-full items-center justify-between"):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(value).classes("text-caption text-right")


def _fmt_entero(v) -> str:
    """Formatea un entero con separador de miles; ``—`` si no es numérico."""
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return "—"


def _render_sintesis(cuadro: dict) -> None:
    """Renderiza el cuadro oficial completo dentro de una card de periodo."""
    capitas = cuadro.get("capitas") or {}
    servicios = cuadro.get("servicios") or {}
    valores = cuadro.get("valores") or {}

    ui.label("Total a pagar").classes("text-caption")
    ui.label(cuadro.get("total_a_pagar", "—")).classes("text-h5 text-primary")

    with ui.grid(columns="repeat(2, minmax(0, 1fr))").classes(
        "w-full gap-x-4 gap-y-1 mt-1"
    ):
        _stat("Cápitas total", _fmt_entero(capitas.get("total")))
        _stat("Servicios total", _fmt_entero(servicios.get("total")))
        _stat("Cápitas básico", _fmt_entero(capitas.get("basico")))
        _stat("Cápitas completo", _fmt_entero(capitas.get("completo")))
        _stat("Cápitas VIP", _fmt_entero(capitas.get("vip")))
        _stat("Cápitas rama 87", _fmt_entero(capitas.get("rama_87")))
        _stat("Cápitas rama 89", _fmt_entero(capitas.get("rama_89")))
        _stat("Cápitas rama 90", _fmt_entero(capitas.get("rama_90")))
        _stat("Coef. uso", str(cuadro.get("coef_uso", "—")))
        _stat("Coef. índice", str(cuadro.get("coef_indice", "—")))
        _stat("Valor básico", str(valores.get("basico", "—")))
        _stat("Valor completo", str(valores.get("completo", "—")))
        _stat("Valor VIP", str(valores.get("vip", "—")))


def _render_card(container: ui.element, p: dict) -> None:
    with (
        container,
        ui.card()
        .classes("w-80 cursor-pointer hover:shadow-md")
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
                    ui.label(f"{p['total']:,.2f}").classes("text-h5 text-primary")
        else:
            ui.label("Sin cierre oficial").classes("text-caption text-grey-7 mt-1")


async def render(_user: dict) -> None:
    items = await _load()
    total_pages = max(1, math.ceil(len(items) / _PAGE_SIZE))

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Periodos").classes("text-h5")
            ui.button("Nuevo periodo", on_click=_crear_periodo)

        container = ui.row().classes("flex-wrap gap-4")

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
