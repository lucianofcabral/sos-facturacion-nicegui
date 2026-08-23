"""Subpage de detalle de un periodo (ciclo).

Consolida la gestión del ciclo: editar datos, cápitas inline por tipo, cierre
(aumento + generar/regenerar) y servicios (import + listado, solo admin).
"""

from __future__ import annotations

from io import BytesIO

from nicegui import ui

from src.application.use_cases import (
    capita_periodo as capita_uc,
)
from src.application.use_cases import (
    cierre as cierre_uc,
)
from src.application.use_cases import (
    periodo as periodo_uc,
)
from src.application.use_cases import (
    servicio as servicio_uc,
)
from src.domain.dto.create import CreateCapitaPeriodo
from src.domain.dto.edit import EditCapitaPeriodo, EditPeriodo
from src.domain.exceptions import PeriodoNotClosedError
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog
from src.ui.session import get_current_rol, get_current_user, is_admin

_PERIODO_FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "anio", "label": "Año", "type": "number", "coerce": "int", "min": 2014, "max": 2100},
    {"key": "mes", "label": "Mes", "type": "number", "coerce": "int", "min": 1, "max": 12},
]

_CIERRE_FIELDS = [
    {"key": "aumento", "label": "Aumento (%)", "type": "number", "coerce": "float", "min": -99.99, "step": 0.01},
    {"key": "motivo", "label": "Motivo", "type": "text"},
]

_SERVICIO_COLUMNS = [
    {"name": "nro_servicio", "label": "N° servicio", "field": "nro_servicio"},
    {"name": "codigo_radio", "label": "Cód. radio", "field": "codigo_radio"},
    {"name": "fecha", "label": "Fecha", "field": "fecha"},
    {"name": "dominio", "label": "Dominio", "field": "dominio"},
    {"name": "cod_productor", "label": "Productor", "field": "cod_productor"},
]


async def _load_periodo(periodo_id: int) -> dict:
    async with PostgresUoW() as uow:
        p = await uow.periodos.get(periodo_id)
        oficial = await uow.cierres.get_oficial(periodo_id)
        total = None
        if oficial is not None and oficial.snapshot:
            sintesis = oficial.snapshot.get("sintesis")
            if sintesis and sintesis.get("total_a_pagar") is not None:
                total = sintesis["total_a_pagar"]
        return {
            "id": p.id,
            "nombre": p.nombre,
            "anio": p.anio,
            "mes": p.mes,
            "cerrado": oficial is not None,
            "total": total,
        }


async def _load_capitas(periodo_id: int) -> list[dict]:
    async with PostgresUoW() as uow:
        items = await capita_uc.listar_capitas_de_periodo(uow, periodo_id)
    return [i.model_dump() for i in items]


async def _load_servicios(periodo_id: int) -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uow.servicios.get_by_fields(periodo_id=periodo_id)
    return [
        {
            "nro_servicio": s.nro_servicio,
            "codigo_radio": s.codigo_radio,
            "fecha": s.fecha.isoformat(),
            "dominio": s.dominio,
            "cod_productor": s.cod_productor,
        }
        for s in items
    ]


async def _guardar_capitas(periodo_id: int, widgets: dict[int, object]) -> None:
    async with PostgresUoW() as uow:
        for tipo_id, widget in widgets.items():
            valor = widget.value
            if valor is None:
                continue
            capitas = int(valor)
            existente = await uow.capitas_periodo.get(periodo_id, tipo_id)
            if existente is None:
                await capita_uc.crear_capita_periodo(
                    uow,
                    CreateCapitaPeriodo(
                        periodo_id=periodo_id, tipo_servicio_id=tipo_id, capitas=capitas
                    ),
                )
            else:
                await capita_uc.editar_capita_periodo(
                    uow, periodo_id, tipo_id, EditCapitaPeriodo(capitas=capitas)
                )
    ui.notify("Cápitas guardadas", type="positive")


async def _editar_datos(periodo: dict) -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await periodo_uc.editar_periodo(
                uow,
                periodo["id"],
                EditPeriodo(
                    nombre=values["nombre"], anio=values["anio"], mes=values["mes"]
                ),
            )
        ui.navigate.reload()

    await open_form_dialog(
        title="Editar datos del período",
        fields=_PERIODO_FIELDS,
        initial={
            "nombre": periodo["nombre"],
            "anio": periodo["anio"],
            "mes": periodo["mes"],
        },
        on_submit=_submit,
    )


async def _cerrar(periodo: dict, *, regenerar: bool) -> None:
    async def _submit(values: dict) -> None:
        aumento = values["aumento"] if values["aumento"] is not None else 0.0
        motivo = values["motivo"] or None
        try:
            async with PostgresUoW() as uow:
                if regenerar:
                    await cierre_uc.generar_nuevo_cierre(
                        uow, periodo["id"], aumento, motivo
                    )
                else:
                    await cierre_uc.cerrar_periodo(uow, periodo["id"], aumento, motivo)
        except PeriodoNotClosedError:
            ui.notify("El período no tiene un cierre oficial", type="negative")
            return
        ui.navigate.reload()

    titulo = "Regenerar cierre" if regenerar else "Generar cierre"
    await open_form_dialog(title=titulo, fields=_CIERRE_FIELDS, on_submit=_submit)


async def _importar(periodo_id: int) -> None:
    """Importación de servicios del periodo (solo admin)."""

    async def _on_upload(e) -> None:
        archivo = BytesIO(await e.file.read())
        try:
            async with PostgresUoW() as uow:
                resultado = await servicio_uc.importar_servicios(
                    uow, periodo_id, archivo, modo.value, rol=get_current_rol()
                )
            pendientes = resultado.get("pendientes", [])
            if pendientes:
                codigos = ", ".join(f"{p['codigo']} ({p['filas']})" for p in pendientes)
                ui.notify(
                    f"Importado con códigos sin resolver: {codigos}",
                    type="warning",
                    timeout=0,
                )
            else:
                ui.notify(
                    f"Importado: {resultado['creados']} creados, "
                    f"{resultado['actualizados']} actualizados",
                    type="positive",
                )
            ui.navigate.reload()
        except Exception as exc:
            ui.notify(f"Error al importar: {exc}", type="negative")

    with ui.row().classes("items-center gap-2"):
        modo = ui.toggle({"upsert": "Upsert", "reemplazo": "Reemplazo"}, value="upsert")
        ui.upload(on_upload=_on_upload, auto_upload=True).props('accept=".xlsx"')


@ui.page("/periodo/{periodo_id}")
async def detalle(periodo_id: int) -> None:
    periodo = await _load_periodo(periodo_id)
    user = get_current_user()
    es_admin = is_admin(user)

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            with ui.row().classes("items-center gap-2"):
                ui.link("← Ciclos", "/").classes("text-caption")
                ui.label(periodo["nombre"]).classes("text-h5")
                if periodo["cerrado"]:
                    ui.badge("Oficial", color="green")
                else:
                    ui.badge("Abierto", color="grey")
            ui.button("Editar datos", on_click=lambda: _editar_datos(periodo))

        # --- Cápitas ----------------------------------------------------------
        with ui.card().classes("w-full gap-2"):
            ui.label("Cápitas").classes("text-h6")
            capitas = await _load_capitas(periodo_id)
            widgets: dict[int, object] = {}
            for c in capitas:
                with ui.row().classes("items-center gap-2"):
                    ui.label(c["tipo_nombre"]).classes("w-40")
                    widgets[c["tipo_servicio_id"]] = ui.number(
                        value=c["capitas"] if c["capitas"] is not None else 0,
                        min=0,
                    )
            ui.button(
                "Guardar cápitas",
                on_click=lambda: _guardar_capitas(periodo_id, widgets),
            )

        # --- Cierre -----------------------------------------------------------
        with ui.card().classes("w-full gap-2"):
            ui.label("Cierre").classes("text-h6")
            with ui.row().classes("gap-2"):
                ui.button(
                    "Generar cierre", on_click=lambda: _cerrar(periodo, regenerar=False)
                )
                ui.button(
                    "Regenerar cierre", on_click=lambda: _cerrar(periodo, regenerar=True)
                )
            if periodo["total"] is not None:
                ui.label(f"Total: {periodo['total']}").classes("text-caption")

        # --- Servicios (admin) ------------------------------------------------
        if es_admin:
            with ui.card().classes("w-full gap-2"):
                ui.label("Servicios").classes("text-h6")
                await _importar(periodo_id)
                ui.table(
                    rows=await _load_servicios(periodo_id), columns=_SERVICIO_COLUMNS
                ).classes("w-full")
