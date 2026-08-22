"""Cargas de opciones para los combos dependientes (claves foráneas)."""

from __future__ import annotations

from src.application.use_cases import periodo as periodo_uc
from src.application.use_cases import tipo_servicio as ts_uc
from src.infrastructure.adapters.uow import PostgresUoW


async def periodo_options() -> list[tuple[int, str]]:
    async with PostgresUoW() as uow:
        items = await periodo_uc.listar_periodos(uow)
    return [(p.id, f"{p.nombre} ({p.anio}-{p.mes:02d})") for p in items]


async def tipo_servicio_options() -> list[tuple[int, str]]:
    async with PostgresUoW() as uow:
        items = await ts_uc.listar_tipos_servicio(uow)
    return [(t.id, t.nombre) for t in items]
