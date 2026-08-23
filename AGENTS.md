# Instrucciones para el agente — sos-facturacion-nicegui

## Memoria del proyecto (Engram)

Este proyecto usa **Engram** como memoria persistente entre sesiones.
El binario está en `/home/fexa/.local/bin/engram`.

**Al inicio de cada sesión**, antes de hacer cualquier cosa, ejecutá:

```bash
engram search "sos-facturacion-nicegui" --project sos-facturacion-nicegui --limit 20
```

Esto te da contexto acumulado sobre arquitectura, decisiones, problemas pendientes y cambios ya realizados. Usá esa información para no repetir análisis ni rehacer trabajo ya hecho.

**Al terminar cambios relevantes**, guardá una memoria:

```bash
engram save "<título descriptivo>" "<detalle>" --project sos-facturacion-nicegui --type <tipo>
```

Tipos disponibles: `context`, `architecture`, `decision`, `issue`, `fix`.

---

## Proyecto

- **Nombre:** Sistema de facturación SOS
- **Stack:** Python 3.13 · NiceGUI · PostgreSQL
- **Gestor de Ambientes:** Astral uv
- **Sintaxis:** ruff
- **Patrón:** Arquitectura Hexagonal (Ports & Adapters)
- **Entorno virtual:** `.venv/` — usar `.venv/bin/python`

## Estructura de capas

```
src/
├── domain/         # Entities (Pydantic frozen), Ports (Protocol), DTOs, Exceptions, Enums
├── application/    # Use Cases, parsers Excel (servicios, panel histórico)
├── adapters/       # Coleccion de Adapters
├── infrastructure/ # Repos, UoW, DB connection
└── ui/             # NiceGUI pages
```

## Convenciones clave

- El UoW canónico está en `src/infrastructure/adapters/uow.py`. El commit es **siempre explícito** en el use case; `__exit__` solo hace rollback.
- Los use cases reciben `UnitOfWorkPort` (Protocol) — nunca modelos ORM directamente.
- Se usa postgres como base de datos **SIN ORM**

## Fuentes de datos (excels de entrada)

Los workbooks de entrada **NO están en este repo**: viven en el proyecto legado `fapi` (`/home/fexa/R/fapi/`).

- Servicios mensuales: `/home/fexa/R/fapi/migrations/files/{anio}/` (un archivo por mes, 2014-2025). Es el default de `--base` en `scripts/import_historico_servicios.py`.
- Panel histórico (alícuotas/cápitas/aumentos): `/home/fexa/R/fapi/migrations/Panel.xlsm`. Es el default de `--xlsx` en `scripts/seed_historico.py`.
- `/home/fexa/R/fapi/files/excel_sources/{anio}/` es una copia paralela (variantes "formula" y archivos 2026) — **no usar**.

## Migraciones one-off (`scripts/`)

- `seed_historico.py` — siembra el histórico desde `Panel.xlsm` (tipos, periodos, alícuotas, cápitas, cierres).
- `import_historico_servicios.py` — re-importa los 134 meses de servicios a la tabla `servicio` (modo reemplazo). Convierte los `.xls` vía LibreOffice headless (`soffice --convert-to xlsx`).

## Formato de los excels de servicios

Cada workbook tiene **5 hojas**: hoja 0 = referencia de mes, hojas 1-3 = servicios (659 Básico / 660 Completo / 658 Vip), hoja 4 = Síntesis.

- **Formato viejo (2014-2018)**: el código de radio está en la columna `Producto` (no existe columna `Codigo Radio`); columnas `N°Servicio` (con signo de grado `°`), `Dominio`, `Número de Productor`. Muchos son `.xls` (openpyxl no los lee).
- **Formato moderno (2019+)**: columna `Codigo Radio`, `Servicio`, `Patente`, `Productor`. Todos `.xlsx`.

## Resolución de códigos de radio

- Los archivos de servicios solo contienen los códigos `658` (vip), `659` (básico), `660` (completo) y `61` (básico). Las ramas `87/89/90` viven en `Panel.xlsm` (cápitas), no en los archivos de servicios.
- Un código desconocido se resuelve creando **su propia entidad** `tipo_servicio` (categoría según la hoja), NO mapeando al existente. El `61` es básico: ya existe como tipo `Básico 61` (rama Automotores).
- La hoja es la pista: `659 Básico` → básico, `660 Completo` → completo, `658 Vip` → vip.
- La síntesis agrupa por `categoria` (enum `categoria_servicio`), nunca por nombre ni por código.
