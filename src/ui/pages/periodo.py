"""Tabla de gestión de Periodos."""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import cierre as cierre_uc
from src.application.use_cases import periodo as uc
from src.domain.dto.create import CreatePeriodo
from src.domain.dto.edit import EditPeriodo
from src.domain.exceptions import PeriodoNotClosedError
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.tablas import CrudPanel
from src.ui.dialogos import open_form_dialog

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id"},
    {"name": "nombre", "label": "Nombre", "field": "nombre"},
    {"name": "anio", "label": "Año", "field": "anio"},
    {"name": "mes", "label": "Mes", "field": "mes"},
]

FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "anio", "label": "Año", "type": "number", "coerce": "int", "min": 2024, "max": 2100},
    {"key": "mes", "label": "Mes", "type": "number", "coerce": "int", "min": 1, "max": 12},
]

CIERRE_FIELDS = [
    {"key": "aumento", "label": "Aumento (%)", "type": "number", "coerce": "float", "min": -99.99, "step": 0.01},
    {"key": "motivo", "label": "Motivo", "type": "text"},
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_periodos(uow)
    return [
        {"id": p.id, "nombre": p.nombre, "anio": p.anio, "mes": p.mes} for p in items
    ]


async def _submit(values: dict, row: dict | None) -> None:
    async with PostgresUoW() as uow:
        if row is None:
            await uc.crear_periodo(
                uow,
                CreatePeriodo(nombre=values["nombre"], anio=values["anio"], mes=values["mes"]),
            )
        else:
            await uc.editar_periodo(
                uow,
                row["id"],
                EditPeriodo(nombre=values["nombre"], anio=values["anio"], mes=values["mes"]),
            )


async def _delete(row: dict) -> None:
    async with PostgresUoW() as uow:
        await uc.eliminar_periodo(uow, row["id"])


async def _cerrar(row: dict) -> None:
    async def _submit(values: dict) -> None:
        aumento = values["aumento"] if values["aumento"] is not None else 0.0
        async with PostgresUoW() as uow:
            await cierre_uc.cerrar_periodo(
                uow, row["id"], aumento, values["motivo"] or None
            )
        ui.notify("Período cerrado", type="positive")

    await open_form_dialog(
        title="Cerrar período",
        fields=CIERRE_FIELDS,
        on_submit=_submit,
    )


async def _regenerar(row: dict) -> None:
    async def _submit(values: dict) -> None:
        aumento = values["aumento"] if values["aumento"] is not None else 0.0
        try:
            async with PostgresUoW() as uow:
                await cierre_uc.generar_nuevo_cierre(
                    uow, row["id"], aumento, values["motivo"] or None
                )
        except PeriodoNotClosedError:
            ui.notify("El período no tiene un cierre oficial", type="negative")
            return
        ui.notify("Nuevo cierre generado", type="positive")

    await open_form_dialog(
        title="Generar nuevo cierre",
        fields=CIERRE_FIELDS,
        on_submit=_submit,
    )


def _initial(row: dict) -> dict:
    return {"nombre": row["nombre"], "anio": row["anio"], "mes": row["mes"]}


async def render(_user: dict) -> None:
    panel = CrudPanel(
        title="Periodos",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["id"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
        row_actions=[("Cerrar período", _cerrar), ("Generar nuevo cierre", _regenerar)],
    )
    await panel.render()
