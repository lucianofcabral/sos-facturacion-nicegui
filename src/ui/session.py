"""Estado de sesión del usuario autenticado (por cliente NiceGUI)."""

from __future__ import annotations

from nicegui import app

from src.domain.enums import RolUsuario

_KEY = "sos_user"


def set_current_user(nombre: str, rol: RolUsuario) -> None:
    # 'user' (no 'client') persiste entre reloads; requiere storage_secret en ui.run().
    app.storage.user[_KEY] = {"nombre": nombre, "rol": rol.value}


def get_current_user() -> dict | None:
    return app.storage.user.get(_KEY)


def clear_current_user() -> None:
    app.storage.user.pop(_KEY, None)


def is_admin(user: dict | None) -> bool:
    return user is not None and user.get("rol") == RolUsuario.ADMIN.value
