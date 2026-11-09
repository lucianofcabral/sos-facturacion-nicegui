#!/usr/bin/env bash
# Levanta la app SOS Facturación en modo desarrollo.
# Uso: ./scripts/dev.sh
set -euo pipefail

# Ir siempre a la raíz del repo, sin importar desde dónde se invoque.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1. Cargar .env si existe (uv run main.py también lo hace vía python-dotenv).
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "⚠  No existe .env. Copiá .env.example → .env y completá las variables."
fi

# 2. Validar variables mínimas para arrancar.
: "${DATABASE_URL:?DATABASE_URL no está definida (.env)}"
: "${STORAGE_SECRET:?STORAGE_SECRET no está definida (.env)}"
: "${ADMIN_NOMBRE:?ADMIN_NOMBRE no está definida (.env)}"
: "${ADMIN_PASSWORD:?ADMIN_PASSWORD no está definida (.env)}"

# 3. Sincronizar dependencias si el entorno virtual no está listo.
if [[ ! -d .venv ]]; then
  echo "→ Instalando dependencias con uv sync…"
  uv sync
fi

# 4. Verificar que Postgres responda (advertencia, no bloquea).
HOST_DB="$(echo "$DATABASE_URL" | sed -E 's#^[a-z+]+://[^@]*@([^:/]+).*#\1#')"
PORT_DB="$(echo "$DATABASE_URL" | sed -E 's#^[a-z+]+://[^@]*@[^:]+:?([0-9]*).*#\1#')"
PORT_DB="${PORT_DB:-5432}"
if command -v pg_isready >/dev/null 2>&1; then
  if ! pg_isready -h "$HOST_DB" -p "$PORT_DB" -q; then
    echo "⚠  Postgres no responde en $HOST_DB:$PORT_DB — revisá que la base esté arriba."
  fi
else
  echo "ℹ  pg_isready no está instalado; se omite el chequeo de conexión."
fi

# 5. Arrancar la app.
echo "→ Levantando en http://${HOST:-127.0.0.1}:${PORT:-8080}"
exec uv run main.py
