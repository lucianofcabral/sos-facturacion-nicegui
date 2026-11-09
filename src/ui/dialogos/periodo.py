"""Campos y diálogos de periodo y cierre.

El diálogo de cierre (``open_cierre_dialog``) muestra una previsualización en
vivo del cuadro de síntesis vía ``previsualizar_cierre`` (solo lectura) antes de
confirmar. Al regenerar, el cuadro oficial vigente se muestra al lado como
baseline y se agrega la diferencia contra la vista previa, para que la decisión
se tome comparando.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from nicegui import ui

from src.application.use_cases import cierre as cierre_uc
from src.domain.exceptions import PeriodoAlreadyClosedError, PeriodoNotClosedError
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.formatos import format_ars, format_int, format_pct
from src.ui.theme import CATEGORIA_COLORS

PERIODO_FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {
        "key": "anio",
        "label": "Año",
        "type": "number",
        "coerce": "int",
        "min": 2014,
        "max": 2100,
    },
    {
        "key": "mes",
        "label": "Mes",
        "type": "number",
        "coerce": "int",
        "min": 1,
        "max": 12,
    },
]

_CAPTION = "text-caption text-grey-6"
_EYEBROW = "text-caption text-grey-6 text-weight-bold"


def _dec(value) -> Decimal | None:
    """Convierte a ``Decimal`` un importe del cuadro (str 2dp); ``None`` si no
    es numérico."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _seccion(titulo: str) -> None:
    """Separador + encabezado de bloque dentro de un cuadro de síntesis."""
    ui.separator().classes("my-2")
    ui.label(titulo.upper()).classes(_EYEBROW).style("letter-spacing: .07em")


def _kv(etiqueta: str, valor: str, *, color: str | None = None) -> None:
    """Fila etiqueta/valor de un cuadro, con punto de categoría opcional."""
    with (
        ui.row().classes("w-full items-center justify-between no-wrap gap-3"),
        ui.row().classes("items-center gap-2 no-wrap"),
    ):
        if color:
            ui.element("span").classes("sos-dot").style(f"background-color: {color}")
        ui.label(etiqueta).classes("text-caption text-grey-5")
        ui.label(valor).classes("text-body2 sos-num")


def _render_cuadro(
    cuadro: dict,
    *,
    titulo: str,
    badge: str | None = None,
    badge_color: str = "grey-6",
) -> None:
    """Renderiza un cuadro de síntesis agrupado por bloque.

    En vez de 14 pares planos, agrupa en Ajuste (aumento y coeficientes),
    Cápitas y servicios, y Valores, con el total a pagar arriba y destacado.
    """
    capitas = cuadro.get("capitas") or {}
    servicios = cuadro.get("servicios") or {}
    valores = cuadro.get("valores") or {}
    cap_automotores = sum(
        int(capitas.get(k) or 0) for k in ("basico", "completo", "vip")
    )
    cap_ramas = sum(int(capitas.get(k) or 0) for k in ("rama_87", "rama_89", "rama_90"))

    with ui.card().classes("w-full gap-0"), ui.column().classes("p-4 gap-0 w-full"):
        with ui.row().classes("w-full items-center justify-between no-wrap"):
            ui.label(titulo).classes(_EYEBROW).style("letter-spacing: .07em")
            if badge:
                ui.badge(badge, color=badge_color).props("outline")
        ui.label(format_ars(cuadro.get("total_a_pagar"))).classes(
            "text-h6 text-primary text-weight-bold mt-1"
        )
        ui.label(cuadro.get("nombre") or "—").classes(_CAPTION)

        _seccion("Ajuste")
        _kv("Aumento", format_pct(cuadro.get("aumento"), fraction=False))
        _kv("Coef. uso", format_pct(cuadro.get("coef_uso")))
        _kv("Coef. índice", format_pct(cuadro.get("coef_indice")))

        _seccion("Cápitas y servicios")
        _kv("Automotores", format_int(cap_automotores))
        _kv("Ramas varias", format_int(cap_ramas))
        _kv("Servicios", format_int(servicios.get("total")))

        _seccion("Valores")
        for etiqueta, clave in (
            ("Básico", "basico"),
            ("Completo", "completo"),
            ("VIP", "vip"),
        ):
            _kv(
                etiqueta,
                format_ars(valores.get(clave)),
                color=CATEGORIA_COLORS.get(clave),
            )


async def open_cierre_dialog(periodo: dict, *, regenerar: bool) -> None:
    """Diálogo de confirmación de cierre con previsualización del cuadro.

    Muestra el formulario (aumento/motivo) y, en vivo, el cuadro de síntesis que
    produciría el cierre (``previsualizar_cierre``). Confirmar persiste vía
    ``cerrar_periodo`` (alta) o ``generar_nuevo_cierre`` (regenerar); cancelar no
    hace nada. Al regenerar, el cuadro oficial actual se muestra al lado como
    baseline, junto con la diferencia de total.
    """
    titulo = "Regenerar cierre" if regenerar else "Generar cierre"

    oficial = None
    baseline: dict | None = None
    if regenerar:
        async with PostgresUoW() as uow:
            oficial = await uow.cierres.get_oficial(periodo["id"])
            if oficial is not None:
                baseline = await cierre_uc._cuadro_de_cierre(uow, oficial)

    # Al regenerar, el formulario arranca con los valores del cierre oficial
    # vigente: el aumento y el motivo que realmente se aplicaron.
    aumento_inicial = float(oficial.aumento) if oficial is not None else 0.0
    motivo_inicial = (oficial.motivo or "") if oficial is not None else ""

    with ui.dialog() as dialog, ui.card().classes("w-[58rem] max-w-[95vw] gap-0 p-0"):
        # --- encabezado ------------------------------------------------------
        with ui.column().classes("w-full p-5 pb-4 gap-1 border-b border-grey-9"):
            ui.label(titulo).classes("text-h6")
            ui.label(
                f"{periodo['nombre']} · Período {periodo['anio']} / {periodo['mes']}"
            ).classes(_CAPTION)

        # --- cuerpo ----------------------------------------------------------
        with ui.column().classes("w-full p-5 gap-4"):
            with ui.row().classes("w-full items-start gap-4 no-wrap"):
                aumento = (
                    ui.number(
                        label="Aumento (%)",
                        value=aumento_inicial,
                        min=-99.99,
                        step=0.01,
                    )
                    .props("dense outlined")
                    .classes("w-40")
                )
                motivo = (
                    ui.input(label="Motivo (opcional)", value=motivo_inicial)
                    .props("dense outlined")
                    .classes("grow")
                )

            if oficial is not None:
                ui.label(
                    "Precargado del cierre oficial vigente. Cambiá el aumento o "
                    "el motivo si el nuevo cierre difiere."
                ).classes(_CAPTION)

            if regenerar:
                with (
                    ui.row()
                    .classes("w-full items-start gap-2 p-3 rounded-borders")
                    .style(
                        "background: rgba(220,38,38,.10);"
                        " border: 1px solid rgba(220,38,38,.28)"
                    ),
                    ui.icon("warning")
                    .classes("text-primary")
                    .style("font-size: 1.1rem"),
                ):
                    ui.label(
                        "Al confirmar se reemplaza el cierre oficial vigente. "
                        "El cierre anterior queda en el histórico del período."
                    ).classes("text-caption")

            preview = ui.element("div").classes("w-full")

            async def _render_preview() -> None:
                async with PostgresUoW() as uow:
                    cuadro = await cierre_uc.previsualizar_cierre(
                        uow, periodo["id"], aumento.value or 0.0
                    )
                preview.clear()
                with preview:
                    dos_columnas = baseline is not None
                    columnas = (
                        "repeat(2, minmax(0, 1fr))"
                        if dos_columnas
                        else "minmax(0, 1fr)"
                    )
                    with ui.element("div").style(
                        "display:grid;grid-template-columns:"
                        f"{columnas};gap:16px;align-items:start"
                    ):
                        if baseline is not None:
                            _render_cuadro(
                                baseline,
                                titulo="Cuadro oficial actual",
                                badge="vigente",
                            )
                        _render_cuadro(
                            cuadro,
                            titulo="Vista previa",
                            badge="nuevo",
                            badge_color="primary",
                        )

                    if baseline is not None:
                        anterior = _dec(baseline.get("total_a_pagar"))
                        nuevo = _dec(cuadro.get("total_a_pagar"))
                        if anterior is not None and nuevo is not None:
                            diferencia = nuevo - anterior
                            signo = (
                                "+"
                                if diferencia > 0
                                else ("-" if diferencia < 0 else "")
                            )
                            texto = f"{signo}{format_ars(abs(diferencia))}"
                            if anterior:
                                variacion = diferencia / anterior * 100
                                texto += f"  ({signo}{format_pct(variacion, fraction=False)})"
                            color = (
                                "text-primary"
                                if diferencia > 0
                                else (
                                    "text-positive" if diferencia < 0 else "text-grey-6"
                                )
                            )
                            with ui.row().classes(
                                "w-full items-center justify-end gap-3 mt-3 no-wrap"
                            ):
                                ui.label("Diferencia de total").classes(_CAPTION)
                                ui.label(texto).classes(
                                    f"text-subtitle2 text-weight-bold sos-num {color}"
                                )

            aumento.on_value_change(lambda _e: _render_preview())

            await _render_preview()

        # --- pie -------------------------------------------------------------
        with ui.row().classes(
            "w-full items-center justify-end gap-2 p-4 border-t border-grey-9"
        ):
            ui.button("Cancelar", on_click=dialog.close).props("flat color=grey-6")

            async def _aceptar() -> None:
                valor = aumento.value or 0.0
                try:
                    async with PostgresUoW() as uow:
                        if regenerar:
                            await cierre_uc.generar_nuevo_cierre(
                                uow, periodo["id"], valor, motivo.value or None
                            )
                        else:
                            await cierre_uc.cerrar_periodo(
                                uow, periodo["id"], valor, motivo.value or None
                            )
                except PeriodoNotClosedError:
                    ui.notify("El período no tiene un cierre oficial", type="negative")
                    return
                except PeriodoAlreadyClosedError:
                    ui.notify("El período ya tiene un cierre oficial", type="negative")
                    return
                except Exception as exc:  # pragma: no cover - defensivo
                    ui.notify(f"Error al generar el cierre: {exc}", type="negative")
                    return
                ui.notify("Cierre guardado", type="positive")
                dialog.close()
                ui.navigate.reload()

            ui.button(titulo, on_click=_aceptar).props("unelevated color=primary")

    dialog.open()
