"""Use cases for UsuarioApp (gestión + autenticación).

Las operaciones de gestión (crear/editar/eliminar) exigen rol ADMIN; la
autenticación es pública. El llamador entra al UoW y pasa la instancia ya
iniciada; el use case hace commit() explícito y deja el rollback para
__aexit__ si algo falla.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import bcrypt

from src.domain.dto import UsuarioCreate, UsuarioEdit
from src.domain.enums import RolUsuario
from src.domain.exceptions import AuthorizationError
from src.domain.models.user import UsuarioApp
from src.domain.ports.uow import UnitOfWorkPort


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


async def crear_usuario(
    uow: UnitOfWorkPort, dto: UsuarioCreate, actor_rol: RolUsuario
) -> UsuarioApp:
    if actor_rol != RolUsuario.ADMIN:
        raise AuthorizationError("Solo un administrador puede crear usuarios")
    entity = UsuarioApp(
        id=uuid4(),
        nombre=dto.nombre,
        password_hash=_hash_password(dto.password),
        rol=dto.rol,
        email=dto.email,
        activo=True,
    )
    creado = await uow.usuarios.add(entity)
    await uow.commit()
    return creado


async def listar_usuarios(uow: UnitOfWorkPort) -> list[UsuarioApp]:
    return await uow.usuarios.list()


async def editar_usuario(
    uow: UnitOfWorkPort, id: UUID, dto: UsuarioEdit, actor_rol: RolUsuario
) -> UsuarioApp:
    if actor_rol != RolUsuario.ADMIN:
        raise AuthorizationError("Solo un administrador puede editar usuarios")
    existente = await uow.usuarios.get(id)
    password_hash = (
        _hash_password(dto.password) if dto.password is not None else existente.password_hash
    )
    actualizado = UsuarioApp(
        id=existente.id,
        nombre=dto.nombre if dto.nombre is not None else existente.nombre,
        password_hash=password_hash,
        rol=dto.rol if dto.rol is not None else existente.rol,
        email=dto.email if dto.email is not None else existente.email,
        activo=dto.activo if dto.activo is not None else existente.activo,
        creado_en=existente.creado_en,
        actualizado_en=existente.actualizado_en,
    )
    resultado = await uow.usuarios.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_usuario(
    uow: UnitOfWorkPort, id: UUID, actor_id: UUID, actor_rol: RolUsuario
) -> None:
    if actor_rol != RolUsuario.ADMIN:
        raise AuthorizationError("Solo un administrador puede eliminar usuarios")
    if id == actor_id:
        raise AuthorizationError("No podés eliminar tu propia cuenta")
    await uow.usuarios.remove(id)
    await uow.commit()


async def activar_usuario(
    uow: UnitOfWorkPort, id: UUID, actor_id: UUID, actor_rol: RolUsuario
) -> UsuarioApp:
    if actor_rol != RolUsuario.ADMIN:
        raise AuthorizationError("Solo un administrador puede activar usuarios")
    existente = await uow.usuarios.get(id)
    actualizado = UsuarioApp(
        id=existente.id,
        nombre=existente.nombre,
        password_hash=existente.password_hash,
        rol=existente.rol,
        email=existente.email,
        activo=True,
        creado_en=existente.creado_en,
        actualizado_en=existente.actualizado_en,
    )
    resultado = await uow.usuarios.update(actualizado)
    await uow.commit()
    return resultado


async def desactivar_usuario(
    uow: UnitOfWorkPort, id: UUID, actor_id: UUID, actor_rol: RolUsuario
) -> UsuarioApp:
    if actor_rol != RolUsuario.ADMIN:
        raise AuthorizationError("Solo un administrador puede desactivar usuarios")
    if id == actor_id:
        raise AuthorizationError("No podés desactivar tu propia cuenta")
    existente = await uow.usuarios.get(id)
    actualizado = UsuarioApp(
        id=existente.id,
        nombre=existente.nombre,
        password_hash=existente.password_hash,
        rol=existente.rol,
        email=existente.email,
        activo=False,
        creado_en=existente.creado_en,
        actualizado_en=existente.actualizado_en,
    )
    resultado = await uow.usuarios.update(actualizado)
    await uow.commit()
    return resultado


async def autenticar_usuario(
    uow: UnitOfWorkPort, nombre: str, password: str
) -> UsuarioApp:
    usuario = await uow.usuarios.get_by_nombre(nombre)
    if usuario is None or not usuario.activo:
        raise AuthorizationError("Credenciales inválidas")
    if not _verify_password(password, usuario.password_hash):
        raise AuthorizationError("Credenciales inválidas")
    return usuario


async def asegurar_admin_inicial(
    uow: UnitOfWorkPort, nombre: str, password: str
) -> UsuarioApp | None:
    """Crea el usuario admin inicial si no existe (idempotente).

    Pensado para el arranque de la app: NO exige ``actor_rol == ADMIN`` porque
    en el primer arranque no hay nadie logueado. Si el usuario ya existe, no lo
    modifica (no resetea la contraseña), para no pisar cambios manuales.
    """
    existente = await uow.usuarios.get_by_nombre(nombre)
    if existente is not None:
        return None
    entity = UsuarioApp(
        id=uuid4(),
        nombre=nombre,
        password_hash=_hash_password(password),
        rol=RolUsuario.ADMIN,
        email=None,
        activo=True,
    )
    creado = await uow.usuarios.add(entity)
    await uow.commit()
    return creado
