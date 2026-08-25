"""Use cases for Periodo (CRUD + read model con estado)."""

from __future__ import annotations

from decimal import Decimal

from src.application.use_cases.cierre import cuadro_de_snapshot, total_de_snapshot
from src.domain.dto import CreatePeriodo, EditPeriodo
from src.domain.models.entities import Periodo, PeriodoConEstado
from src.domain.ports.uow import UnitOfWorkPort


async def crear_periodo(uow: UnitOfWorkPort, dto: CreatePeriodo) -> Periodo:
    entity = Periodo(nombre=dto.nombre, anio=dto.anio, mes=dto.mes)
    creado = await uow.periodos.add(entity)
    await uow.commit()
    return creado


async def listar_periodos(uow: UnitOfWorkPort) -> list[Periodo]:
    return await uow.periodos.list()


async def listar_periodos_con_estado(uow: UnitOfWorkPort) -> list[PeriodoConEstado]:
    """Return periods sorted desc by ``(anio, mes)`` with close state, total and cuadro.

    ``cerrado`` is True when an official cierre exists; ``total`` is the
    ``total_a_pagar`` of that cierre's snapshot (or None when absent) and
    ``cuadro`` is the full síntesis cuadro (or None when absent).
    """
    periodos = await uow.periodos.list()
    periodos.sort(key=lambda p: (p.anio, p.mes), reverse=True)

    resultado: list[PeriodoConEstado] = []
    for p in periodos:
        assert p.id is not None
        oficial = await uow.cierres.get_oficial(p.id)
        total: Decimal | None = None
        cuadro: dict | None = None
        if oficial is not None:
            total = total_de_snapshot(oficial.snapshot)
            cuadro = cuadro_de_snapshot(oficial.snapshot)
        resultado.append(
            PeriodoConEstado(
                id=p.id,
                nombre=p.nombre,
                anio=p.anio,
                mes=p.mes,
                cerrado=oficial is not None,
                total=total,
                cuadro=cuadro,
            )
        )
    return resultado


async def editar_periodo(
    uow: UnitOfWorkPort, id: int, dto: EditPeriodo
) -> Periodo:
    existente = await uow.periodos.get(id)
    actualizado = Periodo(
        id=existente.id,
        nombre=dto.nombre if dto.nombre is not None else existente.nombre,
        anio=dto.anio if dto.anio is not None else existente.anio,
        mes=dto.mes if dto.mes is not None else existente.mes,
    )
    resultado = await uow.periodos.update(actualizado)
    await uow.commit()
    return resultado


async def eliminar_periodo(uow: UnitOfWorkPort, id: int) -> None:
    await uow.periodos.remove(id)
    await uow.commit()
