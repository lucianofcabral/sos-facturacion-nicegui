"""Página principal: login + shell con tabs por entidad y guarda por rol.

Los imports de ``alicuota``, ``capita_periodo`` y ``servicio`` quedan deprecated
(sus tabs fueron eliminadas del shell) pero se conservan para no romper el
registro de rutas de ``@ui.page``.
"""

from __future__ import annotations

from nicegui import ui

from src.application.use_cases import usuario as usuario_uc
from src.domain.exceptions import AuthorizationError
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes import shell
from src.ui.pages import alicuota as alicuota_page  # noqa: F401
from src.ui.pages import capita_periodo as cp_page  # noqa: F401
from src.ui.pages import periodo_detalle  # noqa: F401  (registra /periodo/{id})
from src.ui.pages import periodos as periodos_page
from src.ui.pages import reportes as reportes_page
from src.ui.pages import servicio as servicio_page  # noqa: F401
from src.ui.pages import tipo_servicio as ts_page
from src.ui.pages import usuario as usuario_page
from src.ui.session import (
    get_current_user,
    is_admin,
    set_current_user,
    usuario_autenticado,
)


@ui.page("/")
async def index() -> None:
    if usuario_autenticado():
        await _render_app(get_current_user())
    else:
        await _render_login()


async def _render_login() -> None:
    with ui.card().classes("w-96 mx-auto mt-24"):
        ui.label("Iniciar sesión").classes("text-h6")
        nombre = ui.input("Usuario")
        password = ui.input("Contraseña", password=True, password_toggle_button=True)

        async def do_login() -> None:
            try:
                async with PostgresUoW() as uow:
                    u = await usuario_uc.autenticar_usuario(
                        uow, nombre.value, password.value
                    )
            except AuthorizationError:
                ui.notify("Credenciales inválidas", type="negative")
                return
            set_current_user(u.id, u.nombre, u.rol)
            ui.notify(f"Bienvenido {u.nombre}", type="positive")
            ui.navigate.reload()

        ui.button("Ingresar", on_click=do_login)


async def _render_app(user: dict) -> None:
    # El shell dibuja header + drawer + tabs y devuelve el elemento de tabs.
    tabs = shell.render(user)

    with ui.tab_panels(tabs, value="periodos").classes("w-full"):
        with ui.tab_panel("periodos"):
            await periodos_page.render(user)
        with ui.tab_panel("ts"):
            await ts_page.render(user)
        with ui.tab_panel("reportes"):
            await reportes_page.render(user)
        if is_admin(user):
            with ui.tab_panel("usuario"):
                await usuario_page.render(user)
