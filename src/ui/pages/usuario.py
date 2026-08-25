"""Gestión de Usuarios (solo rol ADMIN) en cards.

Los usuarios se renderizan como cards (espejando el estilo de tipo de servicio):
los ADMIN arriba y los USUARIO abajo, ordenados por nombre. Cada card muestra
nombre, rol, email y estado, con acciones de edición, activación/desactivación
y baja (contrato de use cases sin cambios).
"""

from __future__ import annotations

from uuid import UUID

from nicegui import ui

from src.application.use_cases import usuario as uc
from src.domain.dto.create import UsuarioCreate
from src.domain.dto.edit import UsuarioEdit
from src.domain.enums import RolUsuario
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.dialogos import open_form_dialog
from src.ui.theme import PRIMARY

FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "password", "label": "Contraseña", "type": "password"},
    {
        "key": "rol",
        "label": "Rol",
        "type": "select",
        "options": lambda: [("admin", "Admin"), ("usuario", "Usuario")],
    },
    {"key": "email", "label": "Email", "type": "text"},
]

# Acento neutral para las cards de rol USUARIO (el ADMIN usa la marca roja).
_ACCENT_USUARIO = "#64748B"


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_usuarios(uow)
    out = [
        {
            "id": str(u.id),
            "nombre": u.nombre,
            "rol": u.rol.value,
            "email": u.email,
            "activo": u.activo,
        }
        for u in items
    ]
    # Admin arriba, usuario abajo; dentro de cada grupo, por nombre.
    out.sort(key=lambda u: (u["rol"] != RolUsuario.ADMIN.value, u["nombre"].lower()))
    return out


def _initial(row: dict) -> dict:
    return {"nombre": row["nombre"], "rol": row["rol"], "email": row["email"] or ""}


async def _open_create(actor: RolUsuario) -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await uc.crear_usuario(
                uow,
                UsuarioCreate(
                    nombre=values["nombre"],
                    password=values["password"],
                    rol=RolUsuario(values["rol"]),
                    email=values["email"] or None,
                ),
                actor_rol=actor,
            )
        ui.navigate.reload()

    await open_form_dialog(title="Nuevo usuario", fields=FIELDS, on_submit=_submit)


async def _open_edit(row: dict, actor: RolUsuario) -> None:
    async def _submit(values: dict) -> None:
        async with PostgresUoW() as uow:
            await uc.editar_usuario(
                uow,
                UUID(row["id"]),
                UsuarioEdit(
                    nombre=values["nombre"],
                    rol=RolUsuario(values["rol"]) if values["rol"] else None,
                    email=values["email"] or None,
                    password=values.get("password") or None,
                ),
                actor_rol=actor,
            )
        ui.navigate.reload()

    await open_form_dialog(
        title="Editar usuario",
        fields=FIELDS,
        initial=_initial(row),
        on_submit=_submit,
    )


async def _delete(row: dict, actor_id: UUID, actor: RolUsuario) -> None:
    try:
        async with PostgresUoW() as uow:
            await uc.eliminar_usuario(
                uow, UUID(row["id"]), actor_id=actor_id, actor_rol=actor
            )
    except Exception as exc:
        ui.notify(f"No se pudo eliminar: {exc}", type="negative")
        return
    ui.navigate.reload()


async def _activar(row: dict, actor_id: UUID, actor: RolUsuario) -> None:
    try:
        async with PostgresUoW() as uow:
            await uc.activar_usuario(
                uow, UUID(row["id"]), actor_id=actor_id, actor_rol=actor
            )
    except Exception as exc:
        ui.notify(f"No se pudo activar: {exc}", type="negative")
        return
    ui.navigate.reload()


async def _desactivar(row: dict, actor_id: UUID, actor: RolUsuario) -> None:
    try:
        async with PostgresUoW() as uow:
            await uc.desactivar_usuario(
                uow, UUID(row["id"]), actor_id=actor_id, actor_rol=actor
            )
    except Exception as exc:
        ui.notify(f"No se pudo desactivar: {exc}", type="negative")
        return
    ui.navigate.reload()


def _render_card(
    container: ui.element, u: dict, actor_id: UUID, actor: RolUsuario
) -> None:
    es_admin = u["rol"] == RolUsuario.ADMIN.value
    accent = PRIMARY if es_admin else _ACCENT_USUARIO
    with ui.card().classes("w-72 gap-2"):
        ui.element("div").classes("w-full").style(
            f"height: 4px; background-color: {accent}; border-radius: 9999px;"
        )
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(u["nombre"]).classes("text-h6")
            ui.badge(
                "Admin" if es_admin else "Usuario", color="red" if es_admin else "grey"
            )
        ui.label(u["email"] or "—").classes("text-caption text-grey-7")
        ui.badge(
            "Activo" if u["activo"] else "Inactivo",
            color="green" if u["activo"] else "grey",
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Editar", on_click=lambda u=u: _open_edit(u, actor)).props(
                "flat dense"
            )
            if u["activo"]:
                ui.button(
                    "Desactivar", on_click=lambda u=u: _desactivar(u, actor_id, actor)
                ).props("flat dense")
            else:
                ui.button(
                    "Activar", on_click=lambda u=u: _activar(u, actor_id, actor)
                ).props("flat dense")
            ui.button(
                "Eliminar", on_click=lambda u=u: _delete(u, actor_id, actor)
            ).props("flat dense")


async def render(user: dict) -> None:
    actor = RolUsuario(user["rol"])
    actor_id = UUID(user["id"])
    items = await _load()

    with ui.column().classes("w-full gap-4"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Usuarios").classes("text-h5")
            ui.button("Nuevo usuario", on_click=lambda: _open_create(actor))

        container = ui.row().classes("w-full flex-wrap gap-4")
        for u in items:
            _render_card(container, u, actor_id, actor)
