"""Subpage de detalle de un periodo (ciclo) — panel de trabajo.

Layout de dos columnas: a la izquierda las cápitas editables (tabla compacta con
servicios y participación) y la tabla de servicios; a la derecha una barra fija
con el resumen del cierre oficial, las acciones de cierre, el import de
servicios y el historial de cierres anteriores. El resumen y las acciones quedan
siempre visibles mientras se editan las cápitas.

Diseño: ``design/periodo-detalle/01-panel-trabajo.html``.
"""

from __future__ import annotations

import os
from datetime import date
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
from src.ui.formatos import format_ars, format_int, format_pct
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

_SERVICIO_PAGE_SIZE = 15

# Grupos de cápitas: automotores en la fila de arriba, ramas varias en la de
# abajo. El orden dentro de cada grupo es por nombre.
_CATEGORIAS_AUTOMOTORES = ("basico", "completo", "vip")
_CATEGORIAS_RAMAS = ("rama_87", "rama_89", "rama_90")
_CATEGORIA_ORDEN = _CATEGORIAS_AUTOMOTORES + _CATEGORIAS_RAMAS

_CAPTION = "text-caption text-grey-6"


# --------------------------------------------------------------------------- #
# Carga de datos
# --------------------------------------------------------------------------- #


async def _load_detalle(periodo_id: int) -> dict:
    """Carga en un solo UoW el período, su cierre oficial, el historial, las
    cápitas y los conteos de servicios por tipo."""
    async with PostgresUoW() as uow:
        p = await uow.periodos.get(periodo_id)
        oficial = await uow.cierres.get_oficial(periodo_id)
        recientes = await uow.cierres.get_oficiales_recientes(periodo_id, limit=4)
        conteos = await uow.servicios.conteo_por_tipo_de_periodo(periodo_id)
        tipos = await uow.tipos_servicio.list()
        capitas = await capita_uc.listar_capitas_de_periodo(uow, periodo_id)

    categoria_by_id = {t.id: t.categoria.value for t in tipos if t.id is not None}
    servicios_por_tipo = {c.tipo_servicio_id: c.total for c in conteos}

    filas = [
        {
            "tipo_servicio_id": c.tipo_servicio_id,
            "tipo_nombre": c.tipo_nombre,
            "capitas": c.capitas,
            "categoria": categoria_by_id.get(c.tipo_servicio_id, "basico"),
            "servicios": servicios_por_tipo.get(c.tipo_servicio_id, 0),
        }
        for c in capitas
    ]
    # Automotores primero, ramas después; dentro de cada grupo por nombre.
    filas.sort(
        key=lambda c: (
            _CATEGORIA_ORDEN.index(c["categoria"])
            if c["categoria"] in _CATEGORIA_ORDEN
            else len(_CATEGORIA_ORDEN),
            c["tipo_nombre"].lower(),
        )
    )

    cuadro = cierre_uc.cuadro_de_snapshot(oficial.snapshot) if oficial else None
    total = cierre_uc.total_de_snapshot(oficial.snapshot) if oficial else None

    return {
        "id": p.id,
        "nombre": p.nombre,
        "anio": p.anio,
        "mes": p.mes,
        "cerrado": oficial is not None,
        "total": total,
        "cuadro": cuadro,
        "filas": filas,
        "historial": [
            {
                "fecha": c.creado_en.strftime("%d/%m/%Y") if c.creado_en else "—",
                "total": cierre_uc.total_de_snapshot(c.snapshot),
            }
            for c in recientes
        ],
    }


async def _cargar_pagina(
    periodo_id: int,
    *,
    texto: str | None = None,
    desde: str | None = None,
    hasta: str | None = None,
    page: int = 1,
    page_size: int = _SERVICIO_PAGE_SIZE,
) -> tuple[list[dict], int]:
    async with PostgresUoW() as uow:
        pagina = await servicio_uc.buscar_servicios(
            uow,
            periodo_id,
            texto=texto,
            desde=date.fromisoformat(desde) if desde else None,
            hasta=date.fromisoformat(hasta) if hasta else None,
            page=page,
            page_size=page_size,
        )
    rows = [
        {
            "nro_servicio": s.nro_servicio,
            "codigo_radio": s.codigo_radio,
            "fecha": s.fecha.isoformat(),
            "dominio": s.dominio,
            "cod_productor": s.cod_productor,
        }
        for s in pagina.rows
    ]
    return rows, pagina.total


# --------------------------------------------------------------------------- #
# Acciones
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Formato
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# Bloques de UI
# --------------------------------------------------------------------------- #


def _render_head(periodo: dict) -> None:
    with ui.row().classes("w-full items-start justify-between gap-4 flex-wrap"):
        with ui.column().classes("gap-0"):
            ui.label("Períodos").classes(_CAPTION)
            with ui.row().classes("items-center gap-2"):
                ui.label(periodo["nombre"]).classes("text-h5")
                ui.badge(
                    "Oficial" if periodo["cerrado"] else "Abierto",
                    color="green" if periodo["cerrado"] else "grey",
                )
            ui.label(f"Período {periodo['anio']} / {periodo['mes']}").classes(_CAPTION)
        ui.button("Editar datos", on_click=lambda: _editar_datos(periodo))


def _th(text: str, *, align_right: bool = False) -> None:
    with ui.element("th").classes("text-right" if align_right else ""):
        ui.label(text)


def _td(text: str, *, align_right: bool = False, extra: str = "") -> None:
    with ui.element("td").classes(
        " ".join(filter(None, ["text-right sos-num" if align_right else "", extra]))
    ):
        ui.label(text)


def _render_capitas_card(periodo_id: int, filas: list[dict]) -> None:
    """Tabla editable de cápitas agrupada en automotores y ramas varias."""
    widgets: dict[int, object] = {}
    total = sum(f["capitas"] or 0 for f in filas)
    total_serv = sum(f["servicios"] for f in filas)
    state = {"dirty": False}
    chip: ui.label | None = None

    def _mark_dirty(_e=None) -> None:
        if not state["dirty"]:
            state["dirty"] = True
            if chip is not None:
                chip.set_visibility(True)

    async def _guardar() -> None:
        await _guardar_capitas(periodo_id, widgets)
        state["dirty"] = False
        if chip is not None:
            chip.set_visibility(False)

    def _filas_de(grupo: tuple[str, ...]) -> list[dict]:
        return [f for f in filas if f["categoria"] in grupo]

    def _fila(c: dict) -> None:
        color = CATEGORIA_COLORS.get(c["categoria"], "#64748B")
        with ui.element("tr"):
            with ui.element("td"), ui.row().classes("items-center gap-2 no-wrap"):
                ui.element("span").classes("sos-dot").style(
                    f"background-color: {color}"
                )
                ui.label(c["tipo_nombre"]).classes("text-body2")
            with ui.element("td").classes("text-right"):
                widgets[c["tipo_servicio_id"]] = (
                    ui.number(
                        value=c["capitas"] if c["capitas"] is not None else 0,
                        min=0,
                        on_change=_mark_dirty,
                    )
                    .props('dense outlined input-class="text-right"')
                    .classes("w-24")
                    .style("margin-left: auto")
                )
            _td(format_int(c["servicios"]), align_right=True)
            participacion = (c["capitas"] or 0) / total * 100 if total else 0
            _td(
                format_pct(participacion / 100),
                align_right=True,
                extra="text-grey-6",
            )

    def _grupo(titulo: str, grupo: list[dict]) -> None:
        """Una columna: título del grupo, filas editables y subtotal."""
        if not grupo:
            return
        sub_cap = sum(c["capitas"] or 0 for c in grupo)
        sub_serv = sum(c["servicios"] for c in grupo)
        with ui.column().classes("gap-1 min-w-0 w-full"):
            ui.label(titulo).classes("sos-group-title")
            with ui.element("table").classes("sos-table"):
                with ui.element("caption").classes("sos-sr"):
                    ui.label(f"Cápitas de {titulo}")
                with ui.element("thead"), ui.element("tr"):
                    _th("Categoría")
                    _th("Cápitas", align_right=True)
                    _th("Servicios", align_right=True)
                    _th("Part.", align_right=True)
                with ui.element("tbody"):
                    for c in grupo:
                        _fila(c)
                with ui.element("tfoot"), ui.element("tr"):
                    _td("Subtotal")
                    _td(format_int(sub_cap), align_right=True)
                    _td(format_int(sub_serv), align_right=True)
                    _td(
                        format_pct(sub_cap / total if total else 0),
                        align_right=True,
                        extra="text-grey-6",
                    )

    with ui.card().classes("w-full gap-0"):
        with ui.row().classes("w-full items-center justify-between p-4 pb-3"):
            with ui.column().classes("gap-0"):
                ui.label("Cápitas del período").classes(
                    "text-subtitle1 text-weight-medium"
                )
                ui.label(
                    "Editá los valores y guardá para recalcular el cierre."
                ).classes(_CAPTION)
            ui.label(
                f"Total {format_int(total)} cápitas · {format_int(total_serv)} servicios"
            ).classes(_CAPTION)

        with ui.element("div").classes("sos-cap-grid px-4"):
            _grupo("Automotores", _filas_de(_CATEGORIAS_AUTOMOTORES))
            _grupo("Ramas varias", _filas_de(_CATEGORIAS_RAMAS))

        with ui.row().classes(
            "w-full items-center gap-2 p-4 pt-3 border-t border-grey-9"
        ):
            chip = ui.label("Cambios sin guardar").classes("text-caption text-amber-6")
            chip.set_visibility(False)
            ui.space()
            ui.button("Descartar", on_click=lambda: ui.navigate.reload()).props(
                "flat color=grey-6"
            )
            ui.button("Guardar cápitas", on_click=_guardar)


def _render_resumen(periodo: dict) -> None:
    """Total, ajuste, coeficientes y valores del cierre oficial vigente."""
    cuadro = periodo["cuadro"] or {}
    capitas = cuadro.get("capitas") or {}
    valores = cuadro.get("valores") or {}
    automotores = sum(int(capitas.get(k) or 0) for k in ("basico", "completo", "vip"))

    with ui.card().classes("w-full gap-0"), ui.column().classes("p-4 gap-0 w-full"):
        ui.label("TOTAL A PAGAR").classes(
            "text-caption text-grey-6 text-weight-bold"
        ).style("letter-spacing: .07em")
        ui.label(format_ars(periodo["total"])).classes(
            "text-h5 text-primary text-weight-bold"
        )
        if periodo["cerrado"]:
            ui.label(
                f"Cierre oficial · {format_int(automotores)} cápitas automotores"
            ).classes(_CAPTION)
        else:
            ui.label("Sin cierre oficial generado").classes(_CAPTION)

        ui.separator().classes("my-3")
        ui.label("AJUSTE").classes("text-caption text-grey-6 text-weight-bold").style(
            "letter-spacing: .07em"
        )
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Aumento").classes("text-body2 text-grey-5")
            ui.label(format_pct(cuadro.get("aumento"), fraction=False)).classes(
                "text-body2 sos-num"
            )
        ui.label(
            "Aplicado en el cierre oficial"
            if periodo["cerrado"]
            else "Sin cierre oficial"
        ).classes("text-caption text-grey-7")
        for etiqueta, clave in (
            ("Coef. uso", "coef_uso"),
            ("Coef. índice", "coef_indice"),
        ):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(etiqueta).classes("text-body2 text-grey-5")
                ui.label(format_pct(cuadro.get(clave))).classes("text-body2 sos-num")

        ui.separator().classes("my-3")
        ui.label("VALORES POR CATEGORÍA").classes(
            "text-caption text-grey-6 text-weight-bold"
        ).style("letter-spacing: .07em")
        for etiqueta, clave in (
            ("Básico", "basico"),
            ("Completo", "completo"),
            ("VIP", "vip"),
        ):
            color = CATEGORIA_COLORS.get(clave, "#64748B")
            with ui.row().classes("w-full items-center justify-between"):
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.element("span").classes("sos-dot").style(
                        f"background-color: {color}"
                    )
                    ui.label(etiqueta).classes("text-body2 text-grey-5")
                ui.label(format_ars(valores.get(clave))).classes("text-body2 sos-num")


def _render_import(periodo_id: int) -> None:
    """Bloque visible de importación de servicios (solo admin)."""

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

    with ui.column().classes("w-full gap-2 pt-3 border-t border-grey-9"):
        ui.label("IMPORTAR SERVICIOS").classes(
            "text-caption text-grey-6 text-weight-bold"
        ).style("letter-spacing: .07em")
        modo = ui.toggle(
            {"upsert": "Upsert", "reemplazo": "Reemplazo"}, value="upsert"
        ).props("dense no-caps")
        ui.upload(
            on_upload=_on_upload,
            auto_upload=True,
            label="Subir .xlsx del período",
        ).props('accept=".xlsx" flat').classes("w-full")
        ui.label(
            "Upsert actualiza los servicios existentes. Reemplazo borra los del "
            "período antes de importar."
        ).classes(_CAPTION)


def _render_cierre(periodo: dict, *, es_admin: bool) -> None:
    con_cierre = periodo["cerrado"]
    with ui.card().classes("w-full gap-0"), ui.column().classes("p-4 gap-2 w-full"):
        ui.label("Cierre").classes("text-subtitle1 text-weight-medium")
        ui.button(
            "Generar cierre" if not con_cierre else "Regenerar cierre",
            on_click=lambda: open_cierre_dialog(periodo, regenerar=con_cierre),
        ).classes("w-full")
        if con_cierre:
            ui.button(
                "Generar nuevo cierre",
                on_click=lambda: open_cierre_dialog(periodo, regenerar=False),
            ).props("flat no-caps").classes("w-full")
        ui.button("Descargar Excel", on_click=lambda: _descargar_excel(periodo)).props(
            "flat no-caps color=grey-5"
        ).classes("w-full")
        if con_cierre:
            ui.label(
                "Regenerar reemplaza el cierre oficial vigente. El anterior "
                "queda en el histórico del período."
            ).classes(_CAPTION)
        if es_admin:
            _render_import(periodo["id"])


def _render_historial(historial: list[dict]) -> None:
    with ui.card().classes("w-full gap-0"), ui.column().classes("p-4 gap-1 w-full"):
        ui.label("Cierres anteriores").classes("text-subtitle1 text-weight-medium")
        if not historial:
            ui.label("No hay cierres anteriores a este período.").classes(_CAPTION)
            return
        for item in historial:
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(item["fecha"]).classes("text-body2 text-grey-5")
                ui.label(format_ars(item["total"])).classes("text-body2 sos-num")


async def _render_servicios(periodo_id: int) -> None:
    with ui.card().classes("w-full gap-0"):
        with ui.row().classes("w-full items-center justify-between p-4 pb-3"):
            ui.label("Servicios del período").classes(
                "text-subtitle1 text-weight-medium"
            )

        with ui.row().classes("w-full items-center gap-2 px-4 pb-3 flex-wrap"):
            texto = (
                ui.input(placeholder="Buscar por texto…")
                .props("dense outlined clearable")
                .classes("w-56")
                .style("min-width: 14rem")
            )
            desde = (
                ui.input(placeholder="Desde")
                .props('dense outlined type="date"')
                .classes("w-40")
            )
            hasta = (
                ui.input(placeholder="Hasta")
                .props('dense outlined type="date"')
                .classes("w-40")
            )
            filtrar_btn = ui.button("Filtrar").props("no-caps")
            limpiar_btn = ui.button("Limpiar").props("flat no-caps color=grey-6")

        rows, total = await _cargar_pagina(periodo_id)

        table = ui.table(
            rows=rows,
            columns=_SERVICIO_COLUMNS,
            pagination={
                "rowsPerPage": _SERVICIO_PAGE_SIZE,
                "page": 1,
                "rowsNumber": total,
            },
            on_pagination_change=lambda e: _on_pagination(e),
        ).classes("w-full")

        async def _fetch(page: int) -> None:
            filas, total_filas = await _cargar_pagina(
                periodo_id,
                texto=(texto.value or "").strip() or None,
                desde=desde.value or None,
                hasta=hasta.value or None,
                page=page,
            )
            table.rows = filas
            table.pagination["page"] = page
            table.pagination["rowsNumber"] = total_filas
            table.update()

        async def _on_pagination(e) -> None:
            await _fetch(int(e.value["page"]))

        async def _aplica_filtros() -> None:
            await _fetch(1)

        async def _limpiar_filtros() -> None:
            texto.value = ""
            desde.value = None
            hasta.value = None
            await _fetch(1)

        filtrar_btn.on_click(_aplica_filtros)
        limpiar_btn.on_click(_limpiar_filtros)


RESPONSE_TIMEOUT = float(os.getenv("RESPONSE_TIMEOUT", "30"))


@ui.page("/periodo/{periodo_id}", response_timeout=RESPONSE_TIMEOUT)
async def detalle(periodo_id: int) -> None:
    if not usuario_autenticado():
        ui.navigate.to("/")
        return
    periodo = await _load_detalle(periodo_id)
    user = get_current_user()
    es_admin = is_admin(user)

    # Mismo shell que el resto de la app (header + drawer) para no perder la
    # navegación al entrar a la subpage. La tab "Periodos" queda activa.
    shell.render_subpage(user, active="periodos")

    with ui.column().classes("w-full gap-4"):
        _render_head(periodo)

        with ui.element("div").classes("sos-panel-grid w-full"):
            # --- columna principal -------------------------------------------
            with ui.column().classes("gap-4 min-w-0 w-full"):
                _render_capitas_card(periodo_id, periodo["filas"])
                if es_admin:
                    await _render_servicios(periodo_id)

            # --- barra lateral fija ------------------------------------------
            with ui.column().classes("sos-panel-side gap-4 w-full"):
                _render_resumen(periodo)
                _render_cierre(periodo, es_admin=es_admin)
                _render_historial(periodo["historial"])
