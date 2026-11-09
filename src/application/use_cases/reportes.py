"""Use cases de Reportes: read-models puros (solo lectura).

``resumen_reportes`` alimenta la tabla clásica (conteos por categoria/periodo y
top productores); ``resumen_dashboard`` reúne lo necesario para el dashboard
(servicios por tipo, serie de periodos con su cuadro de cierre y KPIs). Ninguno
escribe nada.
"""

from __future__ import annotations

from src.application.use_cases import periodo as periodo_uc
from src.domain.models.entities import ResumenDashboard, ResumenReportes
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


async def resumen_dashboard(uow: UnitOfWorkPort) -> ResumenDashboard:
    """Reúne los datos del dashboard de Reportes (solo lectura).

    Combina el conteo por categoria/periodo (servicios por periodo), el conteo
    por tipo de servicio (servicios por tipo) y la lista de periodos con estado
    (cuyo ``cuadro`` de cierre ya trae aumento, capitas, servicios, coeficientes,
    valores y total), más el listado de tipos para el KPI de tipos distintos.
    """
    conteos = await uow.servicios.conteo_por_categoria_periodo()
    conteos_tipo = await uow.servicios.conteo_por_tipo()
    tipos = await uow.tipos_servicio.list()
    periodos = await periodo_uc.listar_periodos_con_estado(uow)

    total_servicios = sum(c.total for c in conteos)
    periodos_con_servicios = len({(c.anio, c.mes) for c in conteos})

    return ResumenDashboard(
        conteos_categoria=conteos,
        conteos_tipo=conteos_tipo,
        periodos=periodos,
        total_servicios=total_servicios,
        periodos_con_servicios=periodos_con_servicios,
        tipos_distintos=len(tipos),
    )
