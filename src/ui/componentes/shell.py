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
    get_current_tab,
    get_current_theme,
    is_admin,
    set_current_tab,
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
    # El header es blanco en tema claro y oscuro en tema oscuro: los íconos y el
    # switch usan colores explícitos para seguir siendo visibles en ambos temas.
    with ui.row().classes("items-center gap-1"):
        ui.icon("light_mode").classes("text-amber-400")
        ui.switch().bind_value(app.storage.user, THEME_KEY).props("dense color=amber")
        ui.icon("dark_mode").classes("text-sky-300")


def _render_header(user: dict) -> None:
    with ui.header().classes("items-center justify-between"):
        ui.label("SOS Facturación").classes("text-h6")
        with ui.row().classes("items-center gap-2"):
            ui.label(f"{user['nombre']} ({user['rol']})")
            _render_theme_toggle()
            ui.button("Salir", on_click=_logout)


def _nav_tabs(user: dict) -> None:
    """Draw the vertical drawer tabs (shared by the main page and subpages)."""
    ui.tab("periodos", "Periodos", icon="calendar_month")
    ui.tab("ts", "Tipos de servicio", icon="sell")
    ui.tab("reportes", "Reportes", icon="insights")
    if is_admin(user):
        ui.tab("usuario", "Usuarios", icon="person")


def render(user: dict) -> Tabs:
    """Render header + drawer and return the ``ui.tabs`` element (main page)."""
    _render_header(user)

    with (
        ui.left_drawer(value=True, fixed=True, bordered=True).classes("w-60"),
        ui.tabs(value=get_current_tab()).props("vertical").classes("w-full") as tabs,
    ):
        _nav_tabs(user)
    tabs.on_value_change(lambda e: set_current_tab(e.value))
    return tabs


def render_subpage(user: dict, active: str = "periodos") -> None:
    """Render header + drawer for a subpage; tabs navigate back to the main page.

    Subpages (e.g. the period detail) live on their own route, so the drawer
    can't switch tab panels locally: selecting a tab stores it and navigates to
    ``/``, which restores it via ``get_current_tab``.
    """
    _render_header(user)

    def _goto(e) -> None:
        set_current_tab(e.value)
        ui.navigate.to("/")

    with (
        ui.left_drawer(value=True, fixed=True, bordered=True).classes("w-60"),
        ui.tabs(value=active, on_change=_goto).props("vertical").classes("w-full"),
    ):
        _nav_tabs(user)
