"""Tabla de gestión de Capita periodo (clave compuesta periodo+tipo_servicio)."""

from __future__ import annotations

from src.application.use_cases import capita_periodo as uc
from src.domain.dto.create import CreateCapitaPeriodo
from src.domain.dto.edit import EditCapitaPeriodo
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.combos import periodo_options, tipo_servicio_options
from src.ui.componentes.tablas import CrudPanel

COLUMNS = [
    {"name": "periodo_id", "label": "Periodo", "field": "periodo_id"},
    {"name": "tipo_servicio_id", "label": "Tipo serv.", "field": "tipo_servicio_id"},
    {"name": "capitas", "label": "Capitas", "field": "capitas"},
]

FIELDS = [
    {"key": "periodo_id", "label": "Periodo", "type": "select", "options": periodo_options},
    {"key": "tipo_servicio_id", "label": "Tipo servicio", "type": "select", "options": tipo_servicio_options},
    {"key": "capitas", "label": "Capitas", "type": "number", "coerce": "int", "min": 0},
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_capitas_periodo(uow)
    return [
        {
            "periodo_id": c.periodo_id,
            "tipo_servicio_id": c.tipo_servicio_id,
            "capitas": c.capitas,
        }
        for c in items
    ]


async def _submit(values: dict, row: dict | None) -> None:
    async with PostgresUoW() as uow:
        if row is None:
            await uc.crear_capita_periodo(
                uow,
                CreateCapitaPeriodo(
                    periodo_id=values["periodo_id"],
                    tipo_servicio_id=values["tipo_servicio_id"],
                    capitas=values["capitas"],
                ),
            )
        else:
            await uc.editar_capita_periodo(
                uow,
                row["periodo_id"],
                row["tipo_servicio_id"],
                EditCapitaPeriodo(capitas=values["capitas"]),
            )


async def _delete(row: dict) -> None:
    async with PostgresUoW() as uow:
        await uc.eliminar_capita_periodo(uow, row["periodo_id"], row["tipo_servicio_id"])


def _initial(row: dict) -> dict:
    return {
        "periodo_id": row["periodo_id"],
        "tipo_servicio_id": row["tipo_servicio_id"],
        "capitas": row["capitas"],
    }


async def render(_user: dict) -> None:
    panel = CrudPanel(
        title="Capita periodo",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["periodo_id", "tipo_servicio_id"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
    )
    await panel.render()
