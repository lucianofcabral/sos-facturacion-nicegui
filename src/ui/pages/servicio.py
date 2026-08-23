"""Tabla de gestión de Servicios + importación desde Excel."""

from __future__ import annotations

from io import BytesIO

from nicegui import ui

from src.application.use_cases import servicio as uc
from src.domain.dto.create import CreateServicio
from src.domain.dto.edit import EditServicio
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.combos import periodo_options, tipo_servicio_options
from src.ui.componentes.tablas import CrudPanel

COLUMNS = [
    {"name": "nro_servicio", "label": "N° servicio", "field": "nro_servicio"},
    {"name": "codigo_radio", "label": "Cód. radio", "field": "codigo_radio"},
    {"name": "fecha", "label": "Fecha", "field": "fecha"},
    {"name": "dominio", "label": "Dominio", "field": "dominio"},
    {"name": "cod_productor", "label": "Cód. productor", "field": "cod_productor"},
    {"name": "periodo_id", "label": "Periodo", "field": "periodo_id"},
    {"name": "tipo_servicio_id", "label": "Tipo serv.", "field": "tipo_servicio_id"},
]

FIELDS = [
    {"key": "nro_servicio", "label": "N° servicio", "type": "text"},
    {"key": "codigo_radio", "label": "Cód. radio", "type": "text"},
    {"key": "fecha", "label": "Fecha", "type": "date"},
    {"key": "dominio", "label": "Dominio", "type": "text"},
    {"key": "cod_productor", "label": "Cód. productor", "type": "number", "coerce": "int"},
    {"key": "periodo_id", "label": "Periodo", "type": "select", "options": periodo_options},
    {"key": "tipo_servicio_id", "label": "Tipo servicio", "type": "select", "options": tipo_servicio_options},
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_servicios(uow)
    return [
        {
            "nro_servicio": s.nro_servicio,
            "codigo_radio": s.codigo_radio,
            "fecha": s.fecha,
            "dominio": s.dominio,
            "cod_productor": s.cod_productor,
            "periodo_id": s.periodo_id,
            "tipo_servicio_id": s.tipo_servicio_id,
        }
        for s in items
    ]


async def _submit(values: dict, row: dict | None) -> None:
    async with PostgresUoW() as uow:
        if row is None:
            await uc.crear_servicio(
                uow,
                CreateServicio(
                    nro_servicio=values["nro_servicio"],
                    codigo_radio=values["codigo_radio"],
                    fecha=values["fecha"],
                    dominio=values["dominio"],
                    cod_productor=values["cod_productor"],
                    periodo_id=values["periodo_id"],
                    tipo_servicio_id=values["tipo_servicio_id"],
                ),
            )
        else:
            await uc.editar_servicio(
                uow,
                values["nro_servicio"],
                EditServicio(
                    nro_servicio=values["nro_servicio"],
                    codigo_radio=values["codigo_radio"],
                    fecha=values["fecha"],
                    dominio=values["dominio"],
                    cod_productor=values["cod_productor"],
                    periodo_id=values["periodo_id"],
                    tipo_servicio_id=values["tipo_servicio_id"],
                ),
            )


async def _delete(row: dict) -> None:
    async with PostgresUoW() as uow:
        await uc.eliminar_servicio(uow, row["nro_servicio"])


def _initial(row: dict) -> dict:
    return {
        "nro_servicio": row["nro_servicio"],
        "codigo_radio": row["codigo_radio"],
        "fecha": row["fecha"],
        "dominio": row["dominio"],
        "cod_productor": row["cod_productor"],
        "periodo_id": row["periodo_id"],
        "tipo_servicio_id": row["tipo_servicio_id"],
    }


async def render(_user: dict) -> None:
    panel = CrudPanel(
        title="Servicios",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["nro_servicio"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
    )
    await panel.render()
    await _render_import()


async def _render_import() -> None:
    """Importación de servicios desde un Excel (.xlsx) con modo upsert/reemplazo."""
    with ui.card().classes("w-full gap-2"):
        ui.label("Importar servicios desde Excel").classes("text-h6")
        modo = ui.toggle({"upsert": "Upsert", "reemplazo": "Reemplazo"}, value="upsert")
        periodo = ui.select(dict(await periodo_options()), label="Periodo")
        resumen = ui.label("")

        async def _on_upload(e) -> None:
            if periodo.value is None:
                ui.notify("Seleccioná un periodo", type="warning")
                return
            archivo = BytesIO(await e.file.read())
            try:
                async with PostgresUoW() as uow:
                    resultado = await uc.importar_servicios(
                        uow, periodo.value, archivo, modo.value
                    )
                resumen.set_text(
                    f"Creados: {resultado['creados']} · "
                    f"Actualizados: {resultado['actualizados']} · "
                    f"Eliminados: {resultado['eliminados']}"
                )
                pendientes = resultado.get("pendientes", [])
                if pendientes:
                    codigos = ", ".join(
                        f"{p['codigo']} ({p['filas']})" for p in pendientes
                    )
                    ui.notify(
                        f"Códigos de radio sin resolver: {codigos}",
                        type="warning",
                        timeout=0,
                    )
            except Exception as exc:
                ui.notify(f"Error al importar: {exc}", type="negative")

        ui.upload(on_upload=_on_upload, auto_upload=True).props(
            'accept=".xlsx"'
        ).classes("max-w-full")
