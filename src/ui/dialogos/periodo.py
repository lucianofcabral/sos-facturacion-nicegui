"""Campos y diálogos de periodo y cierre.

El diálogo de cierre (``open_cierre_dialog``) muestra una previsualización en
vivo del cuadro de síntesis vía ``previsualizar_cierre`` (solo lectura) antes de
confirmar. Al regenerar, también muestra el cuadro oficial actual como baseline.
"""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import cierre as cierre_uc
from src.domain.exceptions import PeriodoAlreadyClosedError, PeriodoNotClosedError
from src.infrastructure.adapters.uow import PostgresUoW

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


def _stat(label: str, value: str) -> None:
    """Par label/valor alineado a lo ancho (celda del grid de síntesis)."""
    with ui.row().classes("w-full items-center justify-between"):
        ui.label(label).classes("text-caption text-grey-7")
        ui.label(value).classes("text-caption")


def _render_cuadro(cuadro: dict, titulo: str) -> None:
    """Renderiza un cuadro de síntesis (cápitas, servicios, coef, valores, total)."""
    capitas = cuadro["capitas"]
    servicios = cuadro["servicios"]
    valores = cuadro["valores"]
    ui.label(titulo).classes("text-subtitle2 text-primary")
    with ui.card().classes("w-full"):
        ui.label(cuadro["nombre"]).classes("text-caption text-grey-7")
        stats = [
            ("Aumento", f"{cuadro['aumento']} %"),
            ("Coef. uso", cuadro["coef_uso"]),
            ("Coef. índice", cuadro["coef_indice"]),
            ("Cápitas total", f"{capitas['total']:,}"),
            ("Servicios total", f"{servicios['total']:,}"),
            ("Cápitas básico", f"{capitas['basico']:,}"),
            ("Cápitas completo", f"{capitas['completo']:,}"),
            ("Cápitas VIP", f"{capitas['vip']:,}"),
            ("Servicios básico", f"{servicios['basico']:,}"),
            ("Servicios completo", f"{servicios['completo']:,}"),
            ("Servicios VIP", f"{servicios['vip']:,}"),
            ("Valor básico", valores["basico"]),
            ("Valor completo", valores["completo"]),
            ("Valor VIP", valores["vip"]),
        ]
        with ui.grid(columns="repeat(2, minmax(0, 1fr))").classes(
            "w-full gap-x-6 gap-y-1"
        ):
            for label, value in stats:
                _stat(label, value)
        with ui.row().classes("w-full items-center justify-between mt-2 pt-2 border-t"):
            ui.label("Total a pagar").classes("text-subtitle2")
            ui.label(cuadro["total_a_pagar"]).classes("text-h6 text-primary")


async def open_cierre_dialog(periodo: dict, *, regenerar: bool) -> None:
    """Diálogo de confirmación de cierre con previsualización del cuadro.

    Muestra el formulario (aumento/motivo) y, en vivo, el cuadro de síntesis que
    produciría el cierre (``previsualizar_cierre``). Confirmar persiste vía
    ``cerrar_periodo`` (alta) o ``generar_nuevo_cierre`` (regenerar); cancelar no
    hace nada. Al regenerar, el cuadro oficial actual se muestra como baseline.
    """
    titulo = "Regenerar cierre" if regenerar else "Generar cierre"

    baseline: dict | None = None
    if regenerar:
        async with PostgresUoW() as uow:
            oficial = await uow.cierres.get_oficial(periodo["id"])
            if oficial is not None:
                baseline = await cierre_uc._cuadro_de_cierre(uow, oficial)

    with ui.dialog() as dialog, ui.card().classes("w-[40rem]"):
        ui.label(titulo).classes("text-h6")

        with ui.row().classes("w-full items-start gap-4"):
            aumento = ui.number(
                label="Aumento (%)", value=0.0, min=-99.99, step=0.01
            ).classes("w-40")
            motivo = ui.input(label="Motivo").classes("grow")

        preview = ui.column().classes("w-full gap-2")

        async def _render_preview() -> None:
            async with PostgresUoW() as uow:
                cuadro = await cierre_uc.previsualizar_cierre(
                    uow, periodo["id"], aumento.value or 0.0
                )
            preview.clear()
            with preview:
                if baseline is not None:
                    _render_cuadro(baseline, "Cuadro oficial actual")
                _render_cuadro(cuadro, "Vista previa")

        aumento.on_value_change(lambda _e: _render_preview())

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancelar", on_click=dialog.close).props("flat")

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

            ui.button("Confirmar", on_click=_aceptar)

        await _render_preview()

    dialog.open()
