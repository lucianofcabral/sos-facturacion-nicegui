"""Tabla de gestión de Tipos de servicio."""

from __future__ import annotations

from src.application.use_cases import tipo_servicio as uc
from src.domain.dto.create import CreateTipoServicio
from src.domain.dto.edit import EditTipoServicio
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.tablas import CrudPanel

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id"},
    {"name": "rama", "label": "Rama", "field": "rama"},
    {"name": "nombre", "label": "Nombre", "field": "nombre"},
    {"name": "codigo", "label": "Código", "field": "codigo"},
    {"name": "categoria", "label": "Categoría", "field": "categoria"},
]

_CATEGORIA_OPTS = [
    ("basico", "Básico"),
    ("completo", "Completo"),
    ("vip", "VIP"),
    ("rama_87", "Rama 87"),
    ("rama_89", "Rama 89"),
    ("rama_90", "Rama 90"),
]

FIELDS = [
    {"key": "rama", "label": "Rama", "type": "text"},
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "codigo", "label": "Código", "type": "text"},
    {
        "key": "categoria",
        "label": "Categoría",
        "type": "select",
        "options": _CATEGORIA_OPTS,
    },
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_tipos_servicio(uow)
    return [
        {
            "id": t.id,
            "rama": t.rama,
            "nombre": t.nombre,
            "codigo": t.codigo,
            "categoria": t.categoria.value,
        }
        for t in items
    ]


async def _submit(values: dict, row: dict | None) -> None:
    async with PostgresUoW() as uow:
        if row is None:
            await uc.crear_tipo_servicio(
                uow,
                CreateTipoServicio(
                    rama=values["rama"],
                    nombre=values["nombre"],
                    codigo=values["codigo"],
                    categoria=values["categoria"],
                ),
            )
        else:
            await uc.editar_tipo_servicio(
                uow,
                row["id"],
                EditTipoServicio(
                    rama=values["rama"],
                    nombre=values["nombre"],
                    codigo=values["codigo"],
                    categoria=values["categoria"],
                ),
            )


async def _delete(row: dict) -> None:
    async with PostgresUoW() as uow:
        await uc.eliminar_tipo_servicio(uow, row["id"])


def _initial(row: dict) -> dict:
    return {
        "rama": row["rama"],
        "nombre": row["nombre"],
        "codigo": row["codigo"],
        "categoria": row["categoria"],
    }


async def _edit_info(row: dict) -> list[dict]:
    async with PostgresUoW() as uow:
        m = await uc.metricas_tipo_servicio(uow, row["id"])
    return [
        {"label": "Servicios asociados", "value": str(m.servicios_asociados)},
        {"label": "Ciclos donde aparece", "value": str(m.ciclos)},
        {"label": "Primer ciclo", "value": m.primer_ciclo or "—"},
        {"label": "Último ciclo", "value": m.ultimo_ciclo or "—"},
    ]


async def render(_user: dict) -> None:
    panel = CrudPanel(
        title="Tipos de servicio",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["id"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
        get_edit_info=_edit_info,
    )
    await panel.render()
