"""Integration tests for TipoServicio.codigo (testcontainers Postgres).

Covers create with codigo, get_by_codigo hit/miss, duplicate-code rejection,
and edit with codigo.
"""

from __future__ import annotations

import pytest
from psycopg.errors import UniqueViolation

from conftest import run_test
from src.application.use_cases import tipo_servicio
from src.domain.dto.create import CreateTipoServicio
from src.domain.dto.edit import EditTipoServicio
from src.infrastructure.adapters.uow import PostgresUoW


def test_crear_con_codigo_persiste():
    async def main():
        async with PostgresUoW() as uow:
            ts = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="659", categoria="basico"),
            )
            assert ts.codigo == "659"
            assert ts.id is not None
            leido = await uow.tipos_servicio.get(ts.id)
            assert leido.codigo == "659"

    run_test(main)


def test_get_by_codigo_hit_and_miss():
    async def main():
        async with PostgresUoW() as uow:
            ts = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="659", categoria="basico"),
            )
            hit = await uow.tipos_servicio.get_by_codigo("659")
            assert hit is not None
            assert hit.id == ts.id
            assert await uow.tipos_servicio.get_by_codigo("999") is None

    run_test(main)


def test_codigo_duplicado_raise():
    async def main():
        async with PostgresUoW() as uow:
            await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="660", categoria="basico"),
            )
        async with PostgresUoW() as uow:
            with pytest.raises(UniqueViolation):
                await tipo_servicio.crear_tipo_servicio(
                    uow,
                    CreateTipoServicio(
                        rama="Automotores", nombre="Completo", codigo="660", categoria="completo"
                    ),
                )

    run_test(main)


def test_editar_codigo():
    async def main():
        async with PostgresUoW() as uow:
            ts = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="659", categoria="basico"),
            )
            editado = await tipo_servicio.editar_tipo_servicio(
                uow, ts.id, EditTipoServicio(codigo="661")
            )
            assert editado.codigo == "661"
            assert editado.rama == "Automotores"
            assert editado.nombre == "Básico"
            assert await uow.tipos_servicio.get_by_codigo("661") is not None

    run_test(main)


def test_crear_con_categoria_persiste():
    async def main():
        async with PostgresUoW() as uow:
            ts = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="659", categoria="basico"),
            )
            assert ts.categoria.value == "basico"
            leido = await uow.tipos_servicio.get(ts.id)
            assert leido.categoria.value == "basico"

    run_test(main)


def test_categoria_invalida_rechazada():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CreateTipoServicio(rama="Automotores", nombre="Básico", codigo="659", categoria="desconocida")
