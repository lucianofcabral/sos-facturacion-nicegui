"""Conteo de servicios por tipo acotado a un período (read model del detalle)."""

from datetime import date

from conftest import run_test
from src.application.use_cases import periodo, servicio, tipo_servicio
from src.domain.dto.create import CreatePeriodo, CreateServicio, CreateTipoServicio
from src.domain.enums import CategoriaServicio, RolUsuario
from src.infrastructure.adapters.uow import PostgresUoW

ADMIN = RolUsuario.ADMIN


def test_conteo_por_tipo_de_periodo_aisla_el_periodo():
    async def main():
        async with PostgresUoW() as uow:
            p1 = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Ene 2026", anio=2026, mes=1)
            )
            p2 = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Feb 2026", anio=2026, mes=2)
            )
            basico = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(
                    rama="Automotores",
                    nombre="Básico 659",
                    codigo="659",
                    categoria=CategoriaServicio.BASICO,
                ),
            )
            vip = await tipo_servicio.crear_tipo_servicio(
                uow,
                CreateTipoServicio(
                    rama="Automotores",
                    nombre="VIP 658",
                    codigo="658",
                    categoria=CategoriaServicio.VIP,
                ),
            )

            for nro in ("S1", "S2", "S3"):
                await servicio.crear_servicio(
                    uow,
                    CreateServicio(
                        nro_servicio=nro,
                        codigo_radio="659",
                        dominio="AB123CD",
                        fecha=date(2026, 1, 5),
                        cod_productor=1,
                        periodo_id=p1.id,
                        tipo_servicio_id=basico.id,
                    ),
                    rol=ADMIN,
                )
            await servicio.crear_servicio(
                uow,
                CreateServicio(
                    nro_servicio="S4",
                    codigo_radio="658",
                    dominio="AC884JK",
                    fecha=date(2026, 1, 6),
                    cod_productor=1,
                    periodo_id=p1.id,
                    tipo_servicio_id=vip.id,
                ),
                rol=ADMIN,
            )
            await servicio.crear_servicio(
                uow,
                CreateServicio(
                    nro_servicio="S5",
                    codigo_radio="659",
                    dominio="AD117LM",
                    fecha=date(2026, 2, 6),
                    cod_productor=1,
                    periodo_id=p2.id,
                    tipo_servicio_id=basico.id,
                ),
                rol=ADMIN,
            )

            # Período 1: solo sus servicios, ordenados por total desc y código.
            conteos = await servicio.conteo_por_tipo_de_periodo(uow, p1.id)
            assert [(c.codigo, c.total) for c in conteos] == [("659", 3), ("658", 1)]
            assert conteos[0].categoria is CategoriaServicio.BASICO
            assert conteos[0].tipo_servicio_id == basico.id

            # Período 2: no filtra servicios del período 1.
            conteos_p2 = await servicio.conteo_por_tipo_de_periodo(uow, p2.id)
            assert [(c.codigo, c.total) for c in conteos_p2] == [("659", 1)]

            # Período sin servicios: lista vacía, sin ceros inventados.
            p3 = await periodo.crear_periodo(
                uow, CreatePeriodo(nombre="Mar 2026", anio=2026, mes=3)
            )
            assert await servicio.conteo_por_tipo_de_periodo(uow, p3.id) == []

            # Read-only: no altera lo almacenado.
            assert await uow.servicios.search(periodo_id=p1.id) is not None

    run_test(main)
