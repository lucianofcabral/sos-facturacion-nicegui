"""Autorización por rol para use cases de mutación.

Centraliza el chequeo de admin: los use cases protegidos llaman
``requerir_admin(rol)`` antes de escribir, de modo que la regla viva en la capa
de aplicación y no en cada adapter de UI.
"""

from __future__ import annotations

from src.domain.enums import RolUsuario
from src.domain.exceptions import AuthorizationError


def requerir_admin(rol: RolUsuario) -> None:
    """Raise ``AuthorizationError`` unless the actor is an admin."""
    if rol != RolUsuario.ADMIN:
        raise AuthorizationError(
            "Solo administradores pueden realizar esta operación"
        )
