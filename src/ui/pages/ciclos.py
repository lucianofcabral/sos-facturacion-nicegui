"""Vista de ciclos (periodos) en cards paginadas + ruta de detalle.

Los ciclos se listan en orden descendente por (anio, mes) con su estado de
cierre y total. El detalle completo se implementa en un slice posterior; esta
ruta queda como placeholder para poder navegar desde las cards.
"""

from __future__ import annotations

import math

from nicegui import ui

from src.application.use_cases import periodo as periodo_uc
from src.domain.dto.create import CreatePeriodo
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog

_PAGE_SIZE = 12

_PERIODO_FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "anio", "label": "Año", "type": "number", "coerce": "int", "min": 2014, "max": 2100},
    {"key": "mes", "label": "Mes", "type": "number", "coerce": "int", "min": 1, "max": 12},
]


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


async def _crear_ciclo() -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await periodo_uc.crear_periodo(
                uow,
                CreatePeriodo(nombre=values["nombre"], anio=values["anio"], mes=values["mes"]),
            )
        ui.navigate.reload()

    await open_form_dialog(title="Nuevo ciclo", fields=_PERIODO_FIELDS, on_submit=_submit)


@ui.page("/periodo/{periodo_id}")
async def detalle_periodo(periodo_id: int) -> None:
    """Placeholder del detalle de periodo (se completa en un slice posterior)."""
    with ui.column().classes("w-full gap-2"):
        ui.label(f"Detalle de período #{periodo_id}").classes("text-h5")
        ui.label("La edición completa del ciclo llega en un slice posterior.")


async def render(_user: dict) -> None:
    items = await _load()
    total_pages = max(1, math.ceil(len(items) / _PAGE_SIZE))

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Ciclos").classes("text-h5")
            ui.button("Nuevo ciclo", on_click=_crear_ciclo)

        container = ui.row().classes("flex-wrap gap-4")

        def _render_page(page: int) -> None:
            container.clear()
            start = (page - 1) * _PAGE_SIZE
            with container:
                for p in items[start : start + _PAGE_SIZE]:
                    with ui.card().classes("w-64 cursor-pointer").on(
                        "click", lambda pid=p["id"]: ui.navigate.to(f"/periodo/{pid}")
                    ):
                        ui.label(p["nombre"]).classes("text-h6")
                        ui.label(f"{p['anio']} / {p['mes']}").classes("text-caption")
                        with ui.row().classes("items-center gap-2"):
                            if p["cerrado"]:
                                ui.badge("Oficial", color="green")
                            else:
                                ui.badge("Abierto", color="grey")
                            if p["total"] is not None:
                                ui.label(f"{p['total']:,.2f}").classes("text-caption")

        _render_page(1)

        if total_pages > 1:
            ui.pagination(
                1,
                total_pages,
                direction_links=True,
                on_change=lambda e: _render_page(e.value or 1),
            )
