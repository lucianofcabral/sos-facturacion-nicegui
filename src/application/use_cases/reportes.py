"""Use case de Reportes: resume estadísticas globales de servicios.

Une dos lecturas del repositorio (conteo por categoria/periodo y top
productores) con el listado de tipos de servicio para derivar, en Python, los
KPIs que la vista de Reportes presenta. No escribe nada: es un read-model puro.
"""

from __future__ import annotations

from src.domain.models.entities import ResumenReportes
from src.domain.ports.uow import UnitOfWorkPort

# Límite alto para recuperar TODOS los productores y poder contar los distintos
# sin un query extra; la vista recorta a los 10 primeros para la tabla.
_LIMITE_PRODUCTORES = 10_000


async def resumen_reportes(uow: UnitOfWorkPort) -> ResumenReportes:
    """Calcula el resumen de reportes desde las tablas vivas (solo lectura).

    ``productores_distintos`` se obtiene del largo del listado completo de
    productores (no del top 10) y ``tipos_distintos`` del listado de tipos;
    ambos usan port methods ya existentes (no se agregan queries nuevas).
    """
    conteos = await uow.servicios.conteo_por_categoria_periodo()
    productores = await uow.servicios.top_productores(limite=_LIMITE_PRODUCTORES)
    tipos = await uow.tipos_servicio.list()

    total_servicios = sum(c.total for c in conteos)
    periodos_con_servicios = len({(c.anio, c.mes) for c in conteos})

    return ResumenReportes(
        conteos_categoria=conteos,
        top_productores=productores[:10],
        total_servicios=total_servicios,
        periodos_con_servicios=periodos_con_servicios,
        productores_distintos=len(productores),
        tipos_distintos=len(tipos),
    )
