# Reportes rediseño (Dashboard operativo)

Rediseño de la pestaña Reportes como dashboard (dirección 1 elegida): cantidad de
servicios por tipo, periodo con más servicios, gráfico de valor+aumento (dos
series), cápitas y coeficientes. Reemplaza la tabla "servicios por periodo" y el
"top productores".

## Specs

- S1: "Quisiera que estén datos por tipo de servicio, como santidad de serviciis"
  (cantidad de servicios) → gráfico de cantidad de servicios por tipo de servicio.
- S2: "periodo con mas servicios" → KPI que lo destaque.
- S3: "graficos de aumentos de valor con dos series: valor + barra aumento podría
  ser" → gráfico dual: valor de alícuota (línea) + aumento % (barras), por periodo.
- S4: "También cápitas" → gráfico de cápitas por tipo/periodo.
- S5: "y también coeficientes" → gráfico de coef_uso y coef_indice por periodo.
- S6: "la tabla de servicios por periodo no sirve, el top de productores tampoco"
  → reemplazar ambos bloques.
- S7: Elección de dirección: "El 1" (Dashboard operativo, artboard
  `design/reportes/01-dashboard-operativo.html`).

## Tasks

- T1 (S1): DTO `ConteoTipoServicio` + método `servicio.conteo_por_tipo()`. Route: inline.
- T2 (S1–S5): use case `resumen_dashboard` (read-model). Route: inline.
- T3 (S1–S7): frontend `src/ui/pages/reportes.py` dashboard con ECharts. Route: inline.
- T4 (S1–S5): tests de integración del read-model. Route: inline.

## Log

- L1: "Bien, Reportes, es totalmente horrible y la tabla de servicios por periodo
  no sirve, el top de productores tampoco. Quisiera que estén datos por tipo de
  servicio, como santidad de serviciis, periodo con mas servicios, graficos de
  aumentos de valor con dos series: valor + barra aumento podría ser. También
  cápitas y también coeficientes. No sé cómo armarlo"
- L2: Elección de dirección: "El 1" → Dashboard operativo.
- L3: Implementado en `df88d67` (feat/reportes-dashboard): T1–T4 completas,
  202 tests en verde. Verificación visual pendiente del usuario en la app local.
- L4: Review nativa (2 lenses) escaló con hallazgo CRÍTICO R3-001 (filtro de año
  eliminado → regresión). Arreglado en `1ecccea`: se restauró el selector de año
  y se corrigió el docstring del port `conteo_por_tipo`. 202 tests en verde.
- L5: Re-review del fix (`review-760e9ff326457a1a`) APROBADA y receipt quemado
  (authority burned). 11 findings advisory no bloqueantes (WARNING/SUGGESTION,
  disposition informational), para trabajo futuro separado.
