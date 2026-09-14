# sos-facturacion-nicegui

Sistema de facturación SOS — Python 3.13 · NiceGUI · PostgreSQL (async psycopg,
sin ORM) · arquitectura hexagonal.

## Stack

- **Python 3.13**, gestionado con [uv](https://docs.astral.sh/uv/)
- **NiceGUI** (UI fullstack)
- **PostgreSQL** con `psycopg` async (sin ORM, SQL crudo)
- **Pydantic v2** para entities/DTOs
- **pytest + testcontainers** para tests contra Postgres real efímero
- **ruff** como linter/formatter

## Requisitos

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL local (o accesible por `DATABASE_URL`)
- Docker (solo para correr los tests, que levantan Postgres con testcontainers)
- LibreOffice headless (solo para el import histórico de `.xls` legados)

## Setup

```bash
# 1. Instalar dependencias
uv sync

# 2. Configurar entorno
cp .env.example .env   # completar DATABASE_URL, ADMIN_PASSWORD, STORAGE_SECRET

# 3. Crear la base y aplicar el schema
psql "$DATABASE_URL" -f src/infrastructure/db/create_db.sql
psql "$DATABASE_URL" -f src/infrastructure/db/schema.sql
```

El schema (`src/infrastructure/db/schema.sql`) es idempotente: usa
`CREATE ... IF NOT EXISTS` y crea los enums, tablas e índices.

## Correr la app

```bash
uv run main.py
```

Abre `http://localhost:8080`. Al arrancar, `bootstrap` crea el usuario admin
definido en `.env` (`ADMIN_NOMBRE` / `ADMIN_PASSWORD`) si no existe.

## Tests

```bash
uv run pytest
```

Los tests levantan un Postgres 16 efímero con testcontainers (requiere Docker),
aplican el schema una vez y truncan las tablas por test. No usan pytest-asyncio:
cada test corre su propio event loop vía el helper `run_test` de `conftest.py`.

```bash
uv run ruff check      # linter
uv run ruff format     # formatter
```

## Estructura (arquitectura hexagonal)

```
src/
├── domain/         # Entities (Pydantic frozen), Ports (Protocol), DTOs, Enums
├── application/    # Use cases, parsers de Excel
├── infrastructure/ # Repos Postgres, UoW, conexión a la base
├── adapters/       # Adapters
└── ui/             # Páginas y componentes NiceGUI
```

Convenciones clave:

- El UoW canónico está en `src/infrastructure/adapters/uow.py`. El commit es
  **siempre explícito** en el use case; `__exit__` solo hace rollback.
- Los use cases reciben `UnitOfWorkPort` (Protocol), nunca modelos ORM.
- PostgreSQL sin ORM: SQL crudo con `psycopg.rows.dict_row`.

## Migraciones one-off (`scripts/`)

### Seed histórico (`seed_historico.py`)

Siembra el histórico completo de facturación (jul-2014 → oct-2025) desde
`Panel.xlsm`:

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

### Import histórico de servicios (`import_historico_servicios.py`)

Re-importa los servicios de cada mes (2014-2025) a la tabla `servicio` en modo
reemplazo:

```bash
uv run scripts/import_historico_servicios.py --dry-run
uv run scripts/import_historico_servicios.py
```

Recorre los workbooks bajo `--base` (default `migrations/files`), convierte los
`.xls` legados vía LibreOffice headless y determina `(anio, mes)` desde la hoja
0. Soporta el formato viejo (2014-2018, columna `Producto`) y el moderno (2019+,
columna `Codigo Radio`). Los meses sin archivo o que no parsean se reportan, no
abortan la corrida.

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
