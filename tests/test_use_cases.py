"""Tests de use cases contra Postgres real (testcontainers)."""

import pytest

from conftest import run_test
from src.application.use_cases import (
    alicuota,
    capita_periodo,
    periodo,
    tipo_servicio,
    usuario,
)
from src.domain.dto.create import (
    CreateAlicuota,
    CreateCapitaPeriodo,
    CreatePeriodo,
    CreateTipoServicio,
    UsuarioCreate,
)
from src.domain.dto.edit import UsuarioEdit
from src.domain.enums import RolUsuario
from src.domain.exceptions import AuthorizationError
from src.infrastructure.adapters.uow import PostgresUoW


def test_periodo_crud():
    async def main():
        async with PostgresUoW() as uow:
            p = await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene-2026", anio=2026, mes=1))
            assert p.id is not None
            assert (await periodo.listar_periodos(uow)) == [p]
            await periodo.eliminar_periodo(uow, p.id)
            assert (await periodo.listar_periodos(uow)) == []

    run_test(main)


def test_usuario_create_and_authenticate():
    async def main():
        async with PostgresUoW() as uow:
            u = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="admin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            assert u.activo is True
            auth = await usuario.autenticar_usuario(uow, "admin", "secret123")
            assert auth.id == u.id

    run_test(main)


def test_authenticate_wrong_password():
    async def main():
        async with PostgresUoW() as uow:
            await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="admin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            with pytest.raises(AuthorizationError):
                await usuario.autenticar_usuario(uow, "admin", "wrongpass")

    run_test(main)


def test_admin_gate_blocks_usuario_creation():
    async def main():
        async with PostgresUoW() as uow:
            with pytest.raises(AuthorizationError):
                await usuario.crear_usuario(
                    uow,
                    UsuarioCreate(nombre="pepe", password="password1", rol=RolUsuario.USUARIO),
                    actor_rol=RolUsuario.USUARIO,
                )

    run_test(main)


def test_usuario_edit_delete_flow():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            u = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="admin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            edited = await usuario.editar_usuario(
                uow, u.id, UsuarioEdit(nombre="root"), actor_rol=RolUsuario.ADMIN
            )
            assert edited.nombre == "root"
            await usuario.eliminar_usuario(
                uow, u.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            assert [x.id for x in await usuario.listar_usuarios(uow)] == [actor.id]

    run_test(main)


def test_activar_usuario():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            await usuario.editar_usuario(
                uow, target.id, UsuarioEdit(activo=False), actor_rol=RolUsuario.ADMIN
            )
            activado = await usuario.activar_usuario(
                uow, target.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            assert activado.activo is True
            assert (await uow.usuarios.get(target.id)).activo is True

    run_test(main)


def test_desactivar_usuario():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            desactivado = await usuario.desactivar_usuario(
                uow, target.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            assert desactivado.activo is False
            assert (await uow.usuarios.get(target.id)).activo is False

    run_test(main)


def test_desactivar_usuario_blocked_login():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            await usuario.desactivar_usuario(
                uow, target.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            with pytest.raises(AuthorizationError):
                await usuario.autenticar_usuario(uow, "target", "secret123")

    run_test(main)


def test_reactivar_restaura_login():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            await usuario.desactivar_usuario(
                uow, target.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            with pytest.raises(AuthorizationError):
                await usuario.autenticar_usuario(uow, "target", "secret123")
            await usuario.activar_usuario(
                uow, target.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            auth = await usuario.autenticar_usuario(uow, "target", "secret123")
            assert auth.id == target.id

    run_test(main)


def test_non_admin_cannot_activate():
    async def main():
        async with PostgresUoW() as uow:
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            non_admin = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="noadmin", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            await usuario.editar_usuario(
                uow, target.id, UsuarioEdit(activo=False), actor_rol=RolUsuario.ADMIN
            )
            with pytest.raises(AuthorizationError):
                await usuario.activar_usuario(
                    uow, target.id, actor_id=non_admin.id, actor_rol=RolUsuario.USUARIO
                )
            assert (await uow.usuarios.get(target.id)).activo is False

    run_test(main)


def test_non_admin_cannot_deactivate():
    async def main():
        async with PostgresUoW() as uow:
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            non_admin = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="noadmin", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            with pytest.raises(AuthorizationError):
                await usuario.desactivar_usuario(
                    uow, target.id, actor_id=non_admin.id, actor_rol=RolUsuario.USUARIO
                )
            assert (await uow.usuarios.get(target.id)).activo is True

    run_test(main)


def test_non_admin_cannot_delete():
    async def main():
        async with PostgresUoW() as uow:
            target = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="target", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            non_admin = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="noadmin", password="secret123", rol=RolUsuario.USUARIO),
                actor_rol=RolUsuario.ADMIN,
            )
            with pytest.raises(AuthorizationError):
                await usuario.eliminar_usuario(
                    uow, target.id, actor_id=non_admin.id, actor_rol=RolUsuario.USUARIO
                )
            assert (await uow.usuarios.get(target.id)).id == target.id

    run_test(main)


def test_self_deactivate_forbidden():
    async def main():
        async with PostgresUoW() as uow:
            admin = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="admin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            with pytest.raises(AuthorizationError):
                await usuario.desactivar_usuario(
                    uow, admin.id, actor_id=admin.id, actor_rol=RolUsuario.ADMIN
                )
            assert (await uow.usuarios.get(admin.id)).activo is True

    run_test(main)


def test_self_delete_forbidden():
    async def main():
        async with PostgresUoW() as uow:
            admin = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="admin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            with pytest.raises(AuthorizationError):
                await usuario.eliminar_usuario(
                    uow, admin.id, actor_id=admin.id, actor_rol=RolUsuario.ADMIN
                )
            assert (await uow.usuarios.get(admin.id)).id == admin.id

    run_test(main)


def test_delete_other_admin_incl_last():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            other = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="otheradmin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            await usuario.eliminar_usuario(
                uow, other.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            assert [x.id for x in await usuario.listar_usuarios(uow)] == [actor.id]

    run_test(main)


def test_deactivate_other_admin_incl_last():
    async def main():
        async with PostgresUoW() as uow:
            actor = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="actor", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            other = await usuario.crear_usuario(
                uow,
                UsuarioCreate(nombre="otheradmin", password="secret123", rol=RolUsuario.ADMIN),
                actor_rol=RolUsuario.ADMIN,
            )
            desactivado = await usuario.desactivar_usuario(
                uow, other.id, actor_id=actor.id, actor_rol=RolUsuario.ADMIN
            )
            assert desactivado.activo is False
            assert (await uow.usuarios.get(actor.id)).activo is True

    run_test(main)


def test_alicuota_bracket_search():
    async def main():
        async with PostgresUoW() as uow:
            per = await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene-2026", anio=2026, mes=1))
            ts = await tipo_servicio.crear_tipo_servicio(
                uow, CreateTipoServicio(rama="Agua", nombre="Luz")
            )
            await alicuota.crear_alicuota(
                uow,
                CreateAlicuota(
                    periodo_id=per.id,
                    tipo_servicio_id=ts.id,
                    coeficiente=0.5,
                    valor=10.0,
                ),
            )
            found = await alicuota.buscar_alicuota_por_coeficiente(uow, per.id, ts.id, 0.4)
            assert found is not None and found.coeficiente == 0.5

    run_test(main)


def test_capita_periodo_crud():
    async def main():
        async with PostgresUoW() as uow:
            per = await periodo.crear_periodo(uow, CreatePeriodo(nombre="Ene-2026", anio=2026, mes=1))
            ts = await tipo_servicio.crear_tipo_servicio(
                uow, CreateTipoServicio(rama="Agua", nombre="Agua")
            )
            cp = await capita_periodo.crear_capita_periodo(
                uow,
                CreateCapitaPeriodo(periodo_id=per.id, tipo_servicio_id=ts.id, capitas=100),
            )
            assert cp is not None
            await capita_periodo.eliminar_capita_periodo(uow, per.id, ts.id)
            assert (await capita_periodo.listar_capitas_periodo(uow)) == []

    run_test(main)
