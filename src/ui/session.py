"""Estado de sesión del usuario autenticado (por cliente NiceGUI)."""

from __future__ import annotations

from uuid import UUID

from nicegui import app

from src.domain.enums import RolUsuario

_KEY = "sos_user"

THEME_KEY = "sos_theme"


def set_current_user(id: UUID, nombre: str, rol: RolUsuario) -> None:
    # 'user' (no 'client') persiste entre reloads; requiere storage_secret en ui.run().
    app.storage.user[_KEY] = {"id": str(id), "nombre": nombre, "rol": rol.value}


def get_current_user() -> dict | None:
    return app.storage.user.get(_KEY)


def usuario_autenticado() -> bool:
    """True si hay un usuario logueado con id válido.

    Limpia la sesión si existe un usuario "stale" (dict sin ``id``) para no
    arrastrar un login inválido entre rutas.
    """
    user = get_current_user()
    if user is None:
        return False
    if user.get("id") is None:
        clear_current_user()
        return False
    return True


def clear_current_user() -> None:
    app.storage.user.pop(_KEY, None)


def is_admin(user: dict | None) -> bool:
    return user is not None and user.get("rol") == RolUsuario.ADMIN.value


def get_current_rol() -> RolUsuario:
    """Return the current user's role, defaulting to ``USUARIO`` when logged out."""
    user = get_current_user()
    if user is None:
        return RolUsuario.USUARIO
    return RolUsuario(user["rol"])


def get_current_theme() -> bool:
    """Return the persisted dark-mode preference, defaulting to ``True`` (dark)."""
    return bool(app.storage.user.get(THEME_KEY, True))


def set_current_theme(dark: bool) -> None:
    """Persist the dark-mode preference for the current user."""
    app.storage.user[THEME_KEY] = dark


def ensure_theme() -> None:
    """Persist the default dark theme when no preference is stored yet.

    ``main.py`` keeps ``dark=True`` as the initial default; without a stored
    value the dark-mode toggle would bind to ``None`` (auto) and ignore it.
    """
    if THEME_KEY not in app.storage.user:
        set_current_theme(True)
