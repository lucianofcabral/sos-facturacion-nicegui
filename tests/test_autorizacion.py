"""Tests for role-based authorization of alicuota and servicio mutations."""

from __future__ import annotations

from datetime import date
from io import BytesIO

import pytest

from conftest import run_test
from src.application.use_cases import alicuota, periodo, servicio, tipo_servicio
from src.domain.dto.create import (
    CreateAlicuota,
    CreatePeriodo,
    CreateServicio,
    CreateTipoServicio,
)
from src.domain.dto.edit import EditAlicuota
from src.domain.enums import RolUsuario
from src.domain.exceptions import AuthorizationError
from src.infrastructure.adapters.uow import PostgresUoW


async def _base(uow):
    p = await periodo.crear_periodo(
        uow, CreatePeriodo(nombre="Ene", anio=2026, mes=1)
    )
    ts = await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores", nombre="Básico", codigo="659", categoria="basico"
        ),
    )
    return p, ts


def _alicuota_dto(p, ts, valor: float = 10.0) -> CreateAlicuota:
    return CreateAlicuota(
        periodo_id=p.id, tipo_servicio_id=ts.id, coeficiente=0.5, valor=valor
    )


def _servicio_dto(p, ts) -> CreateServicio:
    return CreateServicio(
        nro_servicio="S1",
        codigo_radio="659",
        fecha=date(2026, 1, 1),
        dominio="ABC",
        cod_productor=1,
        periodo_id=p.id,
        tipo_servicio_id=ts.id,
    )


def test_alicuota_admin_puede_crear():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            a = await alicuota.crear_alicuota(
                uow, _alicuota_dto(p, ts), rol=RolUsuario.ADMIN
            )
            assert a.valor == 10.0

    run_test(main)


def test_alicuota_no_admin_crear_bloqueado():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            with pytest.raises(AuthorizationError):
                await alicuota.crear_alicuota(
                    uow, _alicuota_dto(p, ts), rol=RolUsuario.USUARIO
                )
            assert await uow.alicuotas.list() == []

    run_test(main)


def test_alicuota_no_admin_editar_bloqueado():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(
                uow, _alicuota_dto(p, ts), rol=RolUsuario.ADMIN
            )
            with pytest.raises(AuthorizationError):
                await alicuota.editar_alicuota(
                    uow,
                    p.id,
                    ts.id,
                    EditAlicuota(
                        periodo_id=p.id,
                        tipo_servicio_id=ts.id,
                        coeficiente=0.5,
                        valor=20.0,
                    ),
                    rol=RolUsuario.USUARIO,
                )

    run_test(main)


def test_servicio_admin_puede_crear():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            s = await servicio.crear_servicio(
                uow, _servicio_dto(p, ts), rol=RolUsuario.ADMIN
            )
            assert s.nro_servicio == "S1"

    run_test(main)


def test_servicio_no_admin_crear_bloqueado():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            with pytest.raises(AuthorizationError):
                await servicio.crear_servicio(
                    uow, _servicio_dto(p, ts), rol=RolUsuario.USUARIO
                )
            assert await uow.servicios.list() == []

    run_test(main)


def test_servicio_no_admin_importar_bloqueado():
    async def main():
        async with PostgresUoW() as uow:
            p, _ts = await _base(uow)
            with pytest.raises(AuthorizationError):
                await servicio.importar_servicios(
                    uow, p.id, BytesIO(b""), "upsert", rol=RolUsuario.USUARIO
                )

    run_test(main)
