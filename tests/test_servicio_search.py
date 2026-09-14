"""Integration tests for ServicioRepository.search (testcontainers Postgres).

Cubre: slice exacto de página, página fuera de rango, filtro de texto
case-insensitive en las 4 columnas, rango de fechas inclusivo/abierto,
total filtrado y búsqueda read-only (sin commit).
"""

from __future__ import annotations

from datetime import date

from conftest import run_test
from src.application.use_cases import periodo, tipo_servicio
from src.application.use_cases import servicio as servicio_uc
from src.domain.dto.create import CreatePeriodo, CreateTipoServicio
from src.domain.models.entities import Servicio
from src.infrastructure.adapters.uow import PostgresUoW


async def _setup(uow):
    t = await tipo_servicio.crear_tipo_servicio(
        uow,
        CreateTipoServicio(
            rama="Automotores", nombre="basico", codigo="659", categoria="basico"
        ),
    )
    p = await periodo.crear_periodo(
        uow, CreatePeriodo(nombre="Ene 2024", anio=2024, mes=1)
    )
    return p, t


def _servicio(
    nro: str,
    pid: int,
    tid: int,
    *,
    codigo_radio: str = "659",
    fecha: date = date(2024, 1, 15),
    dominio: str = "DOM0001",
    cod_productor: int = 1,
) -> Servicio:
    return Servicio(
        nro_servicio=nro,
        codigo_radio=codigo_radio,
        fecha=fecha,
        dominio=dominio,
        cod_productor=cod_productor,
        periodo_id=pid,
        tipo_servicio_id=tid,
    )


def test_pagina_devuelve_solo_la_pagina_pedida():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            for i in range(45):
                await uow.servicios.add(_servicio(f"S{i:04d}", p.id, t.id))
            await uow.commit()

        async with PostgresUoW() as uow:
            pagina = await uow.servicios.search(p.id, page=3, page_size=15)

        assert pagina.total == 45
        assert [s.nro_servicio for s in pagina.rows] == [
            f"S{i:04d}" for i in range(30, 45)
        ]

    run_test(main)


def test_pagina_fuera_de_rango_devuelve_vacia():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            for i in range(30):
                await uow.servicios.add(_servicio(f"S{i:04d}", p.id, t.id))
            await uow.commit()

        async with PostgresUoW() as uow:
            pagina = await uow.servicios.search(p.id, page=5, page_size=15)

        assert pagina.rows == []
        assert pagina.total == 30

    run_test(main)


def test_filtro_texto_case_insensitive_en_4_columnas():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            await uow.servicios.add(
                _servicio("S1", p.id, t.id, dominio="ABC123", cod_productor=1)
            )
            await uow.servicios.add(
                _servicio("S2", p.id, t.id, dominio="ZZZ999", cod_productor=2)
            )
            await uow.servicios.add(
                _servicio("900", p.id, t.id, codigo_radio="900", dominio="QQQ111")
            )
            await uow.servicios.add(
                _servicio("S4", p.id, t.id, dominio="WWW222", cod_productor=900)
            )
            await uow.commit()

        async with PostgresUoW() as uow:
            abc = await uow.servicios.search(p.id, texto="abc")
            abc_mayus = await uow.servicios.search(p.id, texto="AbC")
            nueve = await uow.servicios.search(p.id, texto="900")

        assert [s.nro_servicio for s in abc.rows] == ["S1"]
        assert [s.nro_servicio for s in abc_mayus.rows] == ["S1"]
        assert [s.nro_servicio for s in nueve.rows] == ["900", "S4"]

    run_test(main)


def test_filtro_fecha_inclusivo_y_abierto():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            await uow.servicios.add(_servicio("S1", p.id, t.id, fecha=date(2024, 1, 1)))
            await uow.servicios.add(
                _servicio("S2", p.id, t.id, fecha=date(2024, 1, 15))
            )
            await uow.servicios.add(
                _servicio("S3", p.id, t.id, fecha=date(2024, 1, 31))
            )
            await uow.commit()

        async with PostgresUoW() as uow:
            rango = await uow.servicios.search(
                p.id, desde=date(2024, 1, 1), hasta=date(2024, 1, 15)
            )
            solo_desde = await uow.servicios.search(p.id, desde=date(2024, 1, 15))
            solo_hasta = await uow.servicios.search(p.id, hasta=date(2024, 1, 15))

        assert [s.nro_servicio for s in rango.rows] == ["S1", "S2"]
        assert [s.nro_servicio for s in solo_desde.rows] == ["S2", "S3"]
        assert [s.nro_servicio for s in solo_hasta.rows] == ["S1", "S2"]

    run_test(main)


def test_total_refleja_filtros():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            for i in range(40):
                await uow.servicios.add(
                    _servicio(f"T{i:03d}", p.id, t.id, dominio="MATCH")
                )
            for i in range(20):
                await uow.servicios.add(
                    _servicio(f"O{i:03d}", p.id, t.id, dominio="OTRO")
                )
            await uow.commit()

        async with PostgresUoW() as uow:
            filtrado = await uow.servicios.search(
                p.id, texto="match", page=1, page_size=15
            )
            completo = await uow.servicios.search(p.id, page=1, page_size=15)

        assert filtrado.total == 40
        assert len(filtrado.rows) == 15
        assert completo.total == 60

    run_test(main)


def test_buscar_servicios_es_read_only():
    async def main():
        async with PostgresUoW() as uow:
            p, t = await _setup(uow)
            for i in range(3):
                await uow.servicios.add(_servicio(f"S{i}", p.id, t.id))
            await uow.commit()

        async with PostgresUoW() as uow:
            antes = len(await uow.servicios.list())
            pagina = await servicio_uc.buscar_servicios(uow, p.id)
            despues = len(await uow.servicios.list())
            committed = uow._committed

        assert antes == 3
        assert despues == 3
        assert pagina.total == 3
        assert len(pagina.rows) == 3
        assert committed is False

    run_test(main)
