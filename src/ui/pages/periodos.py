"""Vista de periodos en cards paginadas.

Los periodos se listan en orden descendente por (anio, mes) con su estado de
cierre y total. El click en una card navega al detalle del periodo. El total
oficial (``total_a_pagar`` del cierre) se muestra prominente solo en periodos
cerrados.
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


def _render_card(container: ui.element, p: dict) -> None:
    with (
        container,
        ui.card()
        .classes("w-64 cursor-pointer hover:shadow-md")
        .on("click", lambda pid=p["id"]: ui.navigate.to(f"/periodo/{pid}")),
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(p["nombre"]).classes("text-h6")
            if p["cerrado"]:
                ui.badge("Oficial", color="green")
            else:
                ui.badge("Abierto", color="grey")
        ui.label(f"{p['anio']} / {p['mes']}").classes("text-caption")
        if p["cerrado"] and p["total"] is not None:
            with ui.column().classes("mt-2 items-start"):
                ui.label("Total oficial").classes("text-caption")
                ui.label(f"{p['total']:,.2f}").classes("text-h5 text-primary")


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
