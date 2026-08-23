"""Página principal: login + shell con tabs por entidad y guarda por rol."""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import usuario as usuario_uc
from src.domain.exceptions import AuthorizationError
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.pages import alicuota as alicuota_page
from src.ui.pages import capita_periodo as cp_page
from src.ui.pages import periodo_detalle  # noqa: F401  (registra /periodo/{id})
from src.ui.pages import periodos as periodos_page
from src.ui.pages import servicio as servicio_page
from src.ui.pages import tipo_servicio as ts_page
from src.ui.pages import usuario as usuario_page
from src.ui.session import (
    clear_current_user,
    get_current_user,
    is_admin,
    set_current_user,
)


@ui.page("/")
async def index() -> None:
    user = get_current_user()
    if user is None or user.get("id") is None:
        if user is not None:
            clear_current_user()
        await _render_login()
    else:
        await _render_app(user)


async def _render_login() -> None:
    with ui.card().classes("w-96 mx-auto mt-24"):
        ui.label("Iniciar sesión").classes("text-h6")
        nombre = ui.input("Usuario")
        password = ui.input("Contraseña", password=True, password_toggle_button=True)

        async def do_login() -> None:
            try:
                async with PostgresUoW() as uow:
                    u = await usuario_uc.autenticar_usuario(uow, nombre.value, password.value)
            except AuthorizationError:
                ui.notify("Credenciales inválidas", type="negative")
                return
            set_current_user(u.id, u.nombre, u.rol)
            ui.notify(f"Bienvenido {u.nombre}", type="positive")
            ui.navigate.reload()

        ui.button("Ingresar", on_click=do_login)


async def _render_app(user: dict) -> None:
    with ui.header().classes("items-center justify-between"):
        ui.label("SOS Facturación").classes("text-h6")
        with ui.row().classes("items-center gap-2"):
            ui.label(f"{user['nombre']} ({user['rol']})")
            ui.button("Salir", on_click=_logout)

    with ui.left_drawer(value=True, fixed=True, bordered=True).classes(
        "w-60"
    ), ui.tabs().props("vertical").classes("w-full") as tabs:
        ui.tab("periodos", "Periodos", icon="calendar_month")
        ui.tab("ts", "Tipos de servicio")
        ui.tab("alicuota", "Alícuotas")
        ui.tab("servicio", "Servicios")
        ui.tab("capita", "Cápita")
        if is_admin(user):
            ui.tab("usuario", "Usuarios")

    with ui.tab_panels(tabs, value="periodos").classes("w-full"):
        with ui.tab_panel("periodos"):
            await periodos_page.render(user)
        with ui.tab_panel("ts"):
            await ts_page.render(user)
        with ui.tab_panel("alicuota"):
            await alicuota_page.render(user)
        with ui.tab_panel("servicio"):
            await servicio_page.render(user)
        with ui.tab_panel("capita"):
            await cp_page.render(user)
        if is_admin(user):
            with ui.tab_panel("usuario"):
                await usuario_page.render(user)


async def _logout() -> None:
    clear_current_user()
    ui.navigate.reload()
