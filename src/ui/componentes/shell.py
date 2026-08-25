"""Shell compartido: header, drawer con tabs y toggle de tema claro/oscuro.

``render`` dibuja el header (marca, usuario, toggle de tema y logout) y el drawer
lateral con las tabs principales. Devuelve el elemento ``ui.tabs`` para que la
página home arme los ``tab_panel`` correspondientes.
"""

from __future__ import annotations

from nicegui import app, ui
from nicegui.elements.tabs import Tabs

from src.ui.session import (
    THEME_KEY,
    clear_current_user,
    ensure_theme,
    get_current_theme,
    is_admin,
)


async def _logout() -> None:
    clear_current_user()
    ui.navigate.reload()


def _render_theme_toggle() -> None:
    """Toggle de tema claro/oscuro persistido en ``app.storage.user["sos_theme"]``.

    ``ui.dark_mode`` aplica el tema real de la página; el ``ui.switch`` es el
    control visible. Ambos quedan bindeados a la misma clave de storage, así que
    cambiar el switch persiste la preferencia y se restaura al recargar.
    """
    ensure_theme()
    ui.dark_mode(value=get_current_theme()).bind_value(app.storage.user, THEME_KEY)
    with ui.row().classes("items-center gap-1"):
        ui.icon("light_mode")
        ui.switch().bind_value(app.storage.user, THEME_KEY).props("dense")
        ui.icon("dark_mode")


def _render_header(user: dict) -> None:
    with ui.header().classes("items-center justify-between"):
        ui.label("SOS Facturación").classes("text-h6")
        with ui.row().classes("items-center gap-2"):
            ui.label(f"{user['nombre']} ({user['rol']})")
            _render_theme_toggle()
            ui.button("Salir", on_click=_logout)


def render(user: dict) -> Tabs:
    """Render header + drawer y devuelve el elemento ``ui.tabs``."""
    _render_header(user)

    with (
        ui.left_drawer(value=True, fixed=True, bordered=True).classes("w-60"),
        ui.tabs().props("vertical").classes("w-full") as tabs,
    ):
        ui.tab("periodos", "Periodos", icon="calendar_month")
        ui.tab("ts", "Tipos de servicio", icon="sell")
        if is_admin(user):
            ui.tab("usuario", "Usuarios", icon="person")
    return tabs
