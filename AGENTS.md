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
├── application/    # Use Cases, Importador CSV
├── adapters/       # Coleccion de Adapters
├── infrastructure/ # Repos, UoW, DB connection
└── ui/             # NiceGUI pages
```

## Convenciones clave

- El UoW canónico está en `src/infrastructure/adapters/uow.py`. El commit es **siempre explícito** en el use case; `__exit__` solo hace rollback.
- Los use cases reciben `UnitOfWorkPort` (Protocol) — nunca modelos ORM directamente.
- Se usa postgres como base de datos **SIN ORM**
