"""Tabla de gestión de Usuarios (solo rol ADMIN)."""

from __future__ import annotations

from src.application.use_cases import usuario as uc
from src.domain.dto.create import UsuarioCreate
from src.domain.dto.edit import UsuarioEdit
from src.domain.enums import RolUsuario
from src.infrastructure.adapters.uow import PostgresUoW
from src.ui.componentes.tablas import CrudPanel

COLUMNS = [
    {"name": "id", "label": "ID", "field": "id"},
    {"name": "nombre", "label": "Nombre", "field": "nombre"},
    {"name": "rol", "label": "Rol", "field": "rol"},
    {"name": "email", "label": "Email", "field": "email"},
    {"name": "activo", "label": "Activo", "field": "activo"},
]

FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "password", "label": "Contraseña", "type": "password"},
    {"key": "rol", "label": "Rol", "type": "select", "options": lambda: [("admin", "Admin"), ("usuario", "Usuario")]},
    {"key": "email", "label": "Email", "type": "text"},
]


async def _load() -> list[dict]:
    async with PostgresUoW() as uow:
        items = await uc.listar_usuarios(uow)
    return [
        {
            "id": str(u.id),
            "nombre": u.nombre,
            "rol": u.rol.value,
            "email": u.email,
            "activo": u.activo,
        }
        for u in items
    ]


def _initial(row: dict) -> dict:
    return {"nombre": row["nombre"], "rol": row["rol"], "email": row["email"] or ""}


async def render(user: dict) -> None:
    actor = RolUsuario(user["rol"])

    async def _submit(values: dict, row: dict | None) -> None:
        async with PostgresUoW() as uow:
            if row is None:
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
            else:
                await uc.editar_usuario(
                    uow,
                    row["id"],
                    UsuarioEdit(
                        nombre=values["nombre"],
                        rol=RolUsuario(values["rol"]) if values["rol"] else None,
                        email=values["email"] or None,
                        password=values.get("password") or None,
                    ),
                    actor_rol=actor,
                )

    async def _delete(row: dict) -> None:
        async with PostgresUoW() as uow:
            await uc.eliminar_usuario(uow, row["id"], actor_rol=actor)

    panel = CrudPanel(
        title="Usuarios",
        columns=COLUMNS,
        load=_load,
        fields=FIELDS,
        id_keys=["id"],
        on_submit=_submit,
        on_delete=_delete,
        get_initial=_initial,
    )
    await panel.render()
