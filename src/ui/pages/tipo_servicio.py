"""Vista de tipos de servicio en cards coloreadas por categoría.

Cada tipo se renderiza como una card cuyo color deriva de la ``categoria``
(nunca del ``nombre``), reutilizando ``CATEGORIA_COLORS`` de ``src/ui/theme.py``.
La card muestra nombre, código, rama, categoría y las métricas del tipo, con
acciones de edición y eliminación por card (contrato CRUD sin cambios).
"""

from __future__ import annotations

import math

from nicegui import ui

from src.application.use_cases import tipo_servicio as uc
from src.domain.dto.create import CreateTipoServicio
from src.domain.dto.edit import EditTipoServicio
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog
from src.ui.dialogos.tipo_servicio import (
    CATEGORIA_OPTS,
    TIPO_SERVICIO_FIELDS,
    validar_tipo_servicio,
)
from src.ui.theme import CATEGORIA_COLORS

_CATEGORIA_LABELS = dict(CATEGORIA_OPTS)

# Orden estable: automotores (basico/completo/vip) arriba, ramas (87/89/90) abajo.
_CATEGORIA_ORDEN = ("basico", "completo", "vip", "rama_87", "rama_89", "rama_90")


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_tipos_servicio(uow)
        out: list[dict] = []
        for t in items:
            m = await uc.metricas_tipo_servicio(uow, t.id)
            out.append(
                {
                    "id": t.id,
                    "rama": t.rama,
                    "nombre": t.nombre,
                    "codigo": t.codigo,
                    "categoria": t.categoria.value,
                    "servicios": m.servicios_asociados,
                    "ciclos": m.ciclos,
                    "primer": m.primer_ciclo,
                    "ultimo": m.ultimo_ciclo,
                }
            )
    # Agrupa visualmente por categoría en el orden del grid (automotores primero,
    # ramas después) y luego por nombre.
    out.sort(key=lambda d: (_CATEGORIA_ORDEN.index(d["categoria"]), d["nombre"]))
    return out


def _initial(t: dict) -> dict:
    return {
        "rama": t["rama"],
        "nombre": t["nombre"],
        "codigo": t["codigo"],
        "categoria": t["categoria"],
    }


def _edit_info(t: dict) -> list[dict]:
    return [
        {"label": "Servicios asociados", "value": str(t["servicios"])},
        {"label": "Periodos donde aparece", "value": str(t["ciclos"])},
        {"label": "Primer periodo", "value": t["primer"] or "—"},
        {"label": "Último periodo", "value": t["ultimo"] or "—"},
    ]


async def _open_create() -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await uc.crear_tipo_servicio(
                uow,
                CreateTipoServicio(
                    rama=values["rama"],
                    nombre=values["nombre"],
                    codigo=values["codigo"],
                    categoria=values["categoria"],
                ),
            )
        ui.navigate.reload()

    await open_form_dialog(
        title="Nuevo tipo de servicio",
        fields=TIPO_SERVICIO_FIELDS,
        on_submit=_submit,
        on_change=validar_tipo_servicio,
    )


async def _open_edit(t: dict) -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await uc.editar_tipo_servicio(
                uow,
                t["id"],
                EditTipoServicio(
                    rama=values["rama"],
                    nombre=values["nombre"],
                    codigo=values["codigo"],
                    categoria=values["categoria"],
                ),
            )
        ui.navigate.reload()

    await open_form_dialog(
        title="Editar tipo de servicio",
        fields=TIPO_SERVICIO_FIELDS,
        initial=_initial(t),
        info=_edit_info(t),
        on_submit=_submit,
        on_change=validar_tipo_servicio,
    )


async def _delete(t: dict) -> None:
    try:
        async with PostgresUoW() as uow:
            await uc.eliminar_tipo_servicio(uow, t["id"])
    except Exception as exc:
        ui.notify(f"No se pudo eliminar: {exc}", type="negative")
        return
    ui.navigate.reload()


def _render_card(container: ui.element, t: dict) -> None:
    categoria = t["categoria"]
    color = CATEGORIA_COLORS.get(categoria, "#64748B")
    etiqueta = _CATEGORIA_LABELS.get(categoria, categoria)
    with ui.card().classes("w-full gap-2"):
        ui.element("div").classes("w-full").style(
            f"height: 4px; background-color: {color}; border-radius: 9999px;"
        )
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(t["nombre"]).classes("text-h6")
            ui.label(f"Código {t['codigo']}").classes("text-caption text-grey-7")
        with ui.row().classes("items-center gap-1"):
            ui.icon("circle", size="xs").style(f"color: {color}")
            ui.label(etiqueta).classes("text-caption")
        ui.label(t["rama"]).classes("text-caption text-grey-7")
        ui.separator()
        with ui.column().classes("gap-0"):
            ui.label(f"Servicios: {t['servicios']}").classes("text-caption")
            ui.label(f"Periodos: {t['ciclos']}").classes("text-caption")
            ui.label(f"{t['primer'] or '—'} → {t['ultimo'] or '—'}").classes(
                "text-caption text-grey-7"
            )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Editar", on_click=lambda t=t: _open_edit(t)).props("flat dense")
            ui.button("Eliminar", on_click=lambda t=t: _delete(t)).props("flat dense")


async def render(_user: dict) -> None:
    items = await _load()
    # Grid de tantas columnas como haga falta para mostrar todo en exactamente
    # dos filas: automotores arriba y ramas abajo (el orden ya viene de ``_load``).
    columnas = max(1, math.ceil(len(items) / 2))
    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Tipos de servicio").classes("text-h5")
            ui.button("Nuevo tipo", on_click=_open_create)
        container = ui.grid(columns=columnas).classes("w-full gap-4")
        for t in items:
            _render_card(container, t)
