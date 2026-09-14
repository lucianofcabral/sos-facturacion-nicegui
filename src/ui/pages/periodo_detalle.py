"""Subpage de detalle de un periodo (ciclo).

Consolida la gestión del ciclo: editar datos, cápitas inline por categoría,
cierre (aumento + generar/regenerar con previsualización) y servicios (import
+ listado filtrable y paginado, solo admin).
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
from src.ui.componentes import shell
from src.ui.dialogos import open_form_dialog
from src.ui.dialogos.pendientes import resolver_pendientes
from src.ui.dialogos.periodo import PERIODO_FIELDS, open_cierre_dialog
from src.ui.formatos import format_ars
from src.ui.session import (
    get_current_rol,
    get_current_user,
    is_admin,
    usuario_autenticado,
)
from src.ui.theme import CATEGORIA_COLORS

_SERVICIO_COLUMNS = [
    {"name": "nro_servicio", "label": "N° servicio", "field": "nro_servicio"},
    {"name": "codigo_radio", "label": "Cód. radio", "field": "codigo_radio"},
    {"name": "fecha", "label": "Fecha", "field": "fecha"},
    {"name": "dominio", "label": "Dominio", "field": "dominio"},
    {"name": "cod_productor", "label": "Productor", "field": "cod_productor"},
]

# Columnas sobre las que aplica el filtro de texto (LIKE, case-insensitive).
_SERVICIO_TEXT_FIELDS = ("nro_servicio", "codigo_radio", "dominio", "cod_productor")

# Grupos de cápitas: automotores en la fila de arriba, ramas varias en la de
# abajo. El orden dentro de cada grupo es por nombre.
_CATEGORIAS_AUTOMOTORES = ("basico", "completo", "vip")
_CATEGORIAS_RAMAS = ("rama_87", "rama_89", "rama_90")
_CATEGORIA_ORDEN = _CATEGORIAS_AUTOMOTORES + _CATEGORIAS_RAMAS


async def _load_periodo(periodo_id: int) -> dict:
    async with PostgresUoW() as uow:
        p = await uow.periodos.get(periodo_id)
        oficial = await uow.cierres.get_oficial(periodo_id)
        total = cierre_uc.total_de_snapshot(oficial.snapshot) if oficial else None
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
        tipos = await uow.tipos_servicio.list()
    categoria_by_id = {t.id: t.categoria.value for t in tipos if t.id is not None}
    return [
        {
            "tipo_servicio_id": i.tipo_servicio_id,
            "tipo_nombre": i.tipo_nombre,
            "capitas": i.capitas,
            "categoria": categoria_by_id.get(i.tipo_servicio_id, "basico"),
        }
        for i in items
    ]


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
        fields=PERIODO_FIELDS,
        initial={
            "nombre": periodo["nombre"],
            "anio": periodo["anio"],
            "mes": periodo["mes"],
        },
        on_submit=_submit,
    )


async def _descargar_excel(periodo: dict) -> None:
    try:
        async with PostgresUoW() as uow:
            content = await cierre_uc.descargar_cierre_excel(uow, periodo["id"])
    except PeriodoNotClosedError:
        ui.notify("El período no tiene un cierre oficial", type="negative")
        return
    filename = f"cierre_{periodo['nombre'].lower().replace(' ', '_')}.xlsx"
    ui.download(
        content,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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
                resolver_pendientes(pendientes)
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
    if not usuario_autenticado():
        ui.navigate.to("/")
        return
    periodo = await _load_periodo(periodo_id)
    user = get_current_user()
    es_admin = is_admin(user)

    # Mismo shell que el resto de la app (header + drawer) para no perder la
    # navegación al entrar a la subpage. La tab "Periodos" queda activa.
    shell.render_subpage(user, active="periodos")

    with ui.column().classes("w-full gap-4"):
        # --- Encabezado --------------------------------------------------------
        with ui.card().classes("w-full"):  # noqa: SIM117 (nesting preserves the card>row tree)
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(periodo["nombre"]).classes("text-h5")
                        ui.badge(
                            "Oficial" if periodo["cerrado"] else "Abierto",
                            color="green" if periodo["cerrado"] else "grey",
                        )
                    ui.label(f"Período {periodo['anio']} / {periodo['mes']}").classes(
                        "text-caption text-grey-7"
                    )
                with ui.row().classes("items-center gap-4"):
                    if periodo["cerrado"] and periodo["total"] is not None:
                        with ui.column().classes("items-end gap-0"):
                            ui.label("Total oficial").classes(
                                "text-caption text-grey-7"
                            )
                            ui.label(format_ars(periodo["total"])).classes(
                                "text-h5 text-primary"
                            )
                    ui.button("Editar datos", on_click=lambda: _editar_datos(periodo))

        # --- Cápitas + Import (lado a lado) -----------------------------------
        widgets: dict[int, object] = {}
        capitas = await _load_capitas(periodo_id)
        # Automotores primero, ramas después; dentro de cada grupo por nombre.
        capitas.sort(
            key=lambda c: (
                _CATEGORIA_ORDEN.index(c["categoria"])
                if c["categoria"] in _CATEGORIA_ORDEN
                else len(_CATEGORIA_ORDEN),
                c["tipo_nombre"].lower(),
            )
        )
        automotores = [c for c in capitas if c["categoria"] in _CATEGORIAS_AUTOMOTORES]
        ramas = [c for c in capitas if c["categoria"] in _CATEGORIAS_RAMAS]
        # Mismo ancho de tile en ambas filas: tantas columnas como el grupo más
        # grande, así automotores y ramas quedan alineados en dos filas.
        columnas = max(len(automotores), len(ramas), 1)

        def _render_capita(c: dict) -> None:
            color = CATEGORIA_COLORS.get(c["categoria"], "#64748B")
            with ui.card().classes("gap-1"):
                ui.element("div").classes("w-full").style(
                    f"height: 3px; background-color: {color};"
                    " border-radius: 9999px;"
                )
                ui.label(c["tipo_nombre"]).classes("text-caption text-grey-7")
                widgets[c["tipo_servicio_id"]] = ui.number(
                    value=c["capitas"] if c["capitas"] is not None else 0,
                    min=0,
                ).props("dense outlined").classes("w-full")

        with ui.card().classes("w-full gap-3"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Cápitas").classes("text-h6")
                ui.button(
                    "Guardar cápitas",
                    on_click=lambda: _guardar_capitas(periodo_id, widgets),
                )

            # Dos filas: automotores arriba, ramas varias abajo.
            if automotores:
                with ui.grid(columns=columnas).classes("w-full gap-3"):
                    for c in automotores:
                        _render_capita(c)
            if ramas:
                with ui.grid(columns=columnas).classes("w-full gap-3"):
                    for c in ramas:
                        _render_capita(c)

        # --- Cierre + importar servicios (misma fila) -------------------------
        with ui.card().classes("w-full gap-2"):
            ui.label("Cierre").classes("text-h6")
            with ui.row().classes(
                "w-full items-center justify-between gap-4 flex-wrap"
            ):
                with ui.row().classes("items-center gap-2"):
                    ui.button(
                        "Generar cierre",
                        on_click=lambda: open_cierre_dialog(periodo, regenerar=False),
                    )
                    ui.button(
                        "Regenerar cierre",
                        on_click=lambda: open_cierre_dialog(periodo, regenerar=True),
                    )
                    ui.button(
                        "Descargar Excel", on_click=lambda: _descargar_excel(periodo)
                    )
                # Import de servicios en la misma fila que los botones (admin).
                if es_admin:
                    with ui.row().classes("items-center gap-2"):
                        ui.label("Importar servicios").classes(
                            "text-caption text-grey-7"
                        )
                        await _importar(periodo_id)

        # --- Servicios (admin) ------------------------------------------------
        if es_admin:
            with ui.card().classes("w-full gap-3"):
                ui.label("Servicios").classes("text-h6")

                all_rows = await _load_servicios(periodo_id)

                # Todos los filtros + acciones en una única fila horizontal,
                # arriba de la tabla (antes estaban debajo de la paginación).
                with ui.row().classes("w-full items-center gap-2 flex-wrap"):
                    texto = ui.input(placeholder="Buscar por texto…").classes("w-56")
                    desde = ui.input(label="Desde").props('type="date"').classes("w-40")
                    hasta = ui.input(label="Hasta").props('type="date"').classes("w-40")
                    filtrar_btn = ui.button("Filtrar")
                    limpiar_btn = ui.button("Limpiar filtros").props("flat")

                table = ui.table(
                    rows=all_rows,
                    columns=_SERVICIO_COLUMNS,
                    pagination={"rowsPerPage": 15},
                ).classes("w-full")

                def _aplica_filtros() -> None:
                    t = (texto.value or "").strip().lower()
                    rows: list[dict] = []
                    for r in all_rows:
                        if t and not any(
                            t in str(r[c] or "").lower() for c in _SERVICIO_TEXT_FIELDS
                        ):
                            continue
                        if desde.value and r["fecha"] < desde.value:
                            continue
                        if hasta.value and r["fecha"] > hasta.value:
                            continue
                        rows.append(r)
                    table.rows = rows
                    table.update()

                def _limpiar_filtros() -> None:
                    texto.value = ""
                    desde.value = None
                    hasta.value = None
                    _aplica_filtros()

                filtrar_btn.on_click(_aplica_filtros)
                limpiar_btn.on_click(_limpiar_filtros)
