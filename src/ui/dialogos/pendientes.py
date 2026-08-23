"""Diálogo de resolución de códigos pendientes del import de servicios."""

from __future__ import annotations

from nicegui import ui

from src.application.services.excel_servicios import categoria_desde_hoja
from src.application.use_cases import tipo_servicio as tipo_servicio_uc
from src.domain.dto.create import CreateTipoServicio
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog
from src.ui.dialogos.tipo_servicio import TIPO_SERVICIO_FIELDS


def resolver_pendientes(pendientes: list[dict]) -> None:
    """Abre un diálogo que lista los pendientes y ofrece crear cada tipo.

    Cada ``pendiente`` es ``{codigo, filas, hoja}``. El botón "Crear tipo" abre
    el diálogo de alta de tipo pre-cargado: código + categoría según la hoja,
    rama "Automotores".
    """
    if not pendientes:
        return

    with ui.dialog() as dialog, ui.card().classes("w-[28rem]"):
        ui.label("Servicios que necesitan atención").classes("text-h6")
        ui.label(
            "Hay códigos sin tipo de servicio. Creá el tipo y volvé a importar."
        ).classes("text-caption")
        for p in pendientes:
            with ui.row().classes("w-full items-center justify-between gap-2"):
                ui.label(f"{p['codigo']} · {p['filas']} filas · {p['hoja']}").classes(
                    "text-caption"
                )
                ui.button("Crear tipo", on_click=lambda p=p: _crear_tipo(p, dialog))
        ui.button("Cerrar", on_click=dialog.close)
    dialog.open()


async def _crear_tipo(pendiente: dict, dialog_pendientes) -> None:
    categoria = categoria_desde_hoja(pendiente["hoja"])
    dialog_pendientes.close()

    initial: dict = {"codigo": pendiente["codigo"], "rama": "Automotores"}
    if categoria is not None:
        initial["categoria"] = categoria.value

    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await tipo_servicio_uc.crear_tipo_servicio(
                uow,
                CreateTipoServicio(
                    rama=values["rama"],
                    nombre=values["nombre"],
                    codigo=values["codigo"],
                    categoria=values["categoria"],
                ),
            )
        ui.notify(
            f"Tipo '{values['nombre'] or values['codigo']}' creado. Re-importá el archivo.",
            type="positive",
        )

    await open_form_dialog(
        title="Crear tipo de servicio",
        fields=TIPO_SERVICIO_FIELDS,
        initial=initial,
        on_submit=_submit,
    )
