"""Tabla de gestión de Periodos."""

from __future__ import annotations

from src.application.use_cases import periodo as uc
from src.domain.dto.create import CreatePeriodo
from src.domain.dto.edit import EditPeriodo
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.tablas import CrudPanel

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
    )
    await panel.render()
