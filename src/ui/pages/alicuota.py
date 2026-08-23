"""Tabla de gestión de Alícuotas (clave compuesta periodo+tipo_servicio+coeficiente)."""

from __future__ import annotations

from src.application.use_cases import alicuota as uc
from src.domain.dto.create import CreateAlicuota
from src.domain.dto.edit import EditAlicuota
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.combos import periodo_options, tipo_servicio_options
from src.ui.componentes.tablas import CrudPanel
from src.ui.session import get_current_rol

COLUMNS = [
    {"name": "periodo_id", "label": "Periodo", "field": "periodo_id"},
    {"name": "tipo_servicio_id", "label": "Tipo serv.", "field": "tipo_servicio_id"},
    {"name": "coeficiente", "label": "Coeficiente", "field": "coeficiente"},
    {"name": "valor", "label": "Valor", "field": "valor"},
]

FIELDS = [
    {"key": "periodo_id", "label": "Periodo", "type": "select", "options": periodo_options},
    {"key": "tipo_servicio_id", "label": "Tipo servicio", "type": "select", "options": tipo_servicio_options},
    {"key": "coeficiente", "label": "Coeficiente", "type": "number", "coerce": "float", "min": 0, "max": 1, "step": 0.000001},
    {"key": "valor", "label": "Valor", "type": "number", "coerce": "float", "min": 0},
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_alicuotas(uow)
    items.sort(key=lambda a: (a.periodo_id, a.tipo_servicio_id, a.coeficiente))
    return [
        {
            "periodo_id": a.periodo_id,
            "tipo_servicio_id": a.tipo_servicio_id,
            "coeficiente": a.coeficiente,
            "valor": a.valor,
        }
        for a in items
    ]


async def _submit(values: dict, row: dict | None) -> None:
    rol = get_current_rol()
    async with PostgresUoW() as uow:
        if row is None:
            await uc.crear_alicuota(
                uow,
                CreateAlicuota(
                    periodo_id=values["periodo_id"],
                    tipo_servicio_id=values["tipo_servicio_id"],
                    coeficiente=values["coeficiente"],
                    valor=values["valor"],
                ),
                rol=rol,
            )
        else:
            await uc.editar_alicuota(
                uow,
                row["periodo_id"],
                row["tipo_servicio_id"],
                row["coeficiente"],
                EditAlicuota(
                    periodo_id=values["periodo_id"],
                    tipo_servicio_id=values["tipo_servicio_id"],
                    coeficiente=values["coeficiente"],
                    valor=values["valor"],
                ),
                rol=rol,
            )


async def _delete(row: dict) -> None:
    rol = get_current_rol()
    async with PostgresUoW() as uow:
        await uc.eliminar_alicuota(
            uow, row["periodo_id"], row["tipo_servicio_id"], row["coeficiente"], rol=rol
        )


def _initial(row: dict) -> dict:
    return {
        "periodo_id": row["periodo_id"],
        "tipo_servicio_id": row["tipo_servicio_id"],
        "coeficiente": row["coeficiente"],
        "valor": row["valor"],
    }


async def _validar_bracket(values: dict, row: dict | None) -> str | None:
    """Devuelve un mensaje de advertencia si la alícuota rompe la progresión.

    Compara el candidato contra el bracket existente del (periodo, tipo)
    seleccionado. En edición se excluye la alícuota que se está editando.
    """
    periodo_id = values.get("periodo_id")
    tipo_id = values.get("tipo_servicio_id")
    coeficiente = values.get("coeficiente")
    valor = values.get("valor")
    if None in (periodo_id, tipo_id, coeficiente, valor):
        return None
    async with PostgresUoW() as uow:
        actuales = await uow.alicuotas.get_by_keys(
            periodo_id=periodo_id, tipo_servicio_id=tipo_id
        )
    if row is not None:
        actuales = [a for a in actuales if a.coeficiente != row["coeficiente"]]
    ok, mensaje = uc.describir_bracket(
        actuales, coeficiente=coeficiente, valor=valor
    )
    return None if ok else mensaje


async def render(_user: dict) -> None:
    panel = CrudPanel(
        title="Alícuotas",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["periodo_id", "tipo_servicio_id", "coeficiente"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
        on_change=_validar_bracket,
    )
    await panel.render()
