# sos-facturacion-nicegui

Sistema de facturación SOS — Python 3.13 · NiceGUI · PostgreSQL (async psycopg,
sin ORM) · arquitectura hexagonal.

## Seed histórico (Panel.xlsm)

Migración one-off que siembra el histórico completo de facturación
(jul-2014 → oct-2025) desde `Panel.xlsm`:

```bash
# plan sin escribir (recomendado primero)
uv run scripts/seed_historico.py --dry-run

# seed real
uv run scripts/seed_historico.py --xlsx /home/fexa/R/fapi/migrations/Panel.xlsm
```

Qué escribe (fases con commit explícito, en orden):

1. 6 `tipo_servicio` (Básico 659, Completo 660, VIP 658 — Automotores; Rama
   87/89/90 — Ramas Varias)
2. 136 `periodo` 2014-07..2025-10, nombrados `"MES AAAA"` en español mayúsculas
3. 108 `alicuota` jul-2014 (36 coef 0.030–0.065 × 3 prestaciones)
4. 816 `capita_periodo` (6 × 136)
5. replay de 62 aumentos como cierres (137 filas `cierre`: 2022-08 ×2)

La idempotencia se resuelve por guard: si existe algún periodo con `anio` en
[2014, 2025] el seed aborta antes de escribir.

## Drift 2dp aceptado vs legacy

El snapshot redondea `ROUND_HALF_UP` a 2 decimales por mes, lo que acumula una
deriva mínima frente al cálculo legacy de precisión completa. Ejemplo: la
Básica a coef 0.03 cierra en **1463.61** (legacy 1463.87). Es la única ruta
autoconsistente con la columna `NUMERIC(12,2)` de la base. La deriva se
reporta en la salida del script y no viola ninguna restricción de 2dp.

## Rollback runbook

Si el seed falla a mitad de camino (o hay que rehacerlo), revertir el rango
histórico y re-correr:

```sql
-- limpia periodo/alicuota/capita_periodo/cierre del histórico (cascada)
DELETE FROM periodo WHERE anio < 2024;
```

Los datos post-2024 no se tocan (el seed es no-destructivo sobre ese rango).
Si además se revierte la relajación del CHECK:

```sql
-- volver al rango original (solo si no se va a usar histórico)
-- ALTER TABLE periodo DROP CONSTRAINT periodo_anio_check;
-- ALTER TABLE periodo ADD CONSTRAINT periodo_anio_check
--     CHECK (anio BETWEEN 2024 AND 2100);
```

El CHECK en `src/infrastructure/db/schema.sql` quedó en `anio BETWEEN 2014 AND 2100`.
