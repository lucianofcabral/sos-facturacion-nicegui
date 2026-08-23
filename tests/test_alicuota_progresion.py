"""Tests for the alicuota 3-part key and progressive invariant."""

from __future__ import annotations

import pytest

from conftest import run_test
from src.application.use_cases import alicuota, periodo, tipo_servicio
from src.application.use_cases.alicuota import validar_progresion
from src.domain.dto.create import (
    CreateAlicuota,
    CreatePeriodo,
    CreateTipoServicio,
)
from src.domain.dto.edit import EditAlicuota
from src.domain.enums import RolUsuario
from src.domain.exceptions import AlicuotaProgresionError
from src.domain.models.entities import Alicuota
from src.infrastructure.adapters.uow import PostgresUoW


def _a(tipo_id: int, coeficiente: float, valor: float) -> Alicuota:
    return Alicuota(
        periodo_id=1, tipo_servicio_id=tipo_id, coeficiente=coeficiente, valor=valor
    )


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


def _dto(p, ts, coeficiente: float, valor: float) -> CreateAlicuota:
    return CreateAlicuota(
        periodo_id=p.id, tipo_servicio_id=ts.id, coeficiente=coeficiente, valor=valor
    )


# --- validar_progresion (puro) ------------------------------------------------


def test_validar_progresion_ok():
    validar_progresion([_a(1, 0.4, 10.0), _a(1, 0.6, 20.0)])


def test_validar_progresion_violacion():
    with pytest.raises(AlicuotaProgresionError):
        validar_progresion([_a(1, 0.4, 10.0), _a(1, 0.6, 5.0)])


# --- crear con invariante -----------------------------------------------------


def test_crear_alicuota_violacion_bloqueada():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.4, 10.0), rol=RolUsuario.ADMIN)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.6, 20.0), rol=RolUsuario.ADMIN)
            with pytest.raises(AlicuotaProgresionError):
                await alicuota.crear_alicuota(uow, _dto(p, ts, 0.5, 5.0), rol=RolUsuario.ADMIN)
            restantes = await uow.alicuotas.get_by_keys(periodo_id=p.id, tipo_servicio_id=ts.id)
            assert len(restantes) == 2

    run_test(main)


def test_crear_alicuota_monotonica_ok():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.4, 10.0), rol=RolUsuario.ADMIN)
            a = await alicuota.crear_alicuota(uow, _dto(p, ts, 0.6, 20.0), rol=RolUsuario.ADMIN)
            assert a.valor == 20.0

    run_test(main)


# --- editar -------------------------------------------------------------------


def test_editar_alicuota_violacion_bloqueada():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.4, 10.0), rol=RolUsuario.ADMIN)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.6, 20.0), rol=RolUsuario.ADMIN)
            with pytest.raises(AlicuotaProgresionError):
                await alicuota.editar_alicuota(
                    uow, p.id, ts.id, 0.4,
                    EditAlicuota(periodo_id=p.id, tipo_servicio_id=ts.id, coeficiente=0.4, valor=99.0),
                    rol=RolUsuario.ADMIN,
                )

    run_test(main)


def test_editar_alicuota_solo_una():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.4, 10.0), rol=RolUsuario.ADMIN)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.6, 20.0), rol=RolUsuario.ADMIN)
            await alicuota.editar_alicuota(
                uow, p.id, ts.id, 0.4,
                EditAlicuota(periodo_id=p.id, tipo_servicio_id=ts.id, coeficiente=0.4, valor=15.0),
                rol=RolUsuario.ADMIN,
            )
            restantes = await uow.alicuotas.get_by_keys(periodo_id=p.id, tipo_servicio_id=ts.id)
            assert sorted((a.coeficiente, a.valor) for a in restantes) == [(0.4, 15.0), (0.6, 20.0)]

    run_test(main)


def test_eliminar_alicuota_solo_una():
    async def main():
        async with PostgresUoW() as uow:
            p, ts = await _base(uow)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.4, 10.0), rol=RolUsuario.ADMIN)
            await alicuota.crear_alicuota(uow, _dto(p, ts, 0.6, 20.0), rol=RolUsuario.ADMIN)
            await alicuota.eliminar_alicuota(uow, p.id, ts.id, 0.4, rol=RolUsuario.ADMIN)
            restantes = await uow.alicuotas.get_by_keys(periodo_id=p.id, tipo_servicio_id=ts.id)
            assert [(a.coeficiente, a.valor) for a in restantes] == [(0.6, 20.0)]

    run_test(main)
