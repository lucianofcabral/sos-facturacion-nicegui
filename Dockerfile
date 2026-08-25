# Imagen de producción para la app NiceGUI (sos-facturacion).
# Build:  docker build -t fecca81/sos-facturacion:0.1.2 .
# Push:   docker push fecca81/sos-facturacion:0.1.2

FROM python:3.13-slim

# uv como gestor de dependencias (mismo lockfile que en dev)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) Dependencias primero: capa cacheada mientras no cambie el lock
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) Código de la aplicación
COPY main.py ./
COPY src ./src

# Usuario sin privilegios
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["/app/.venv/bin/python", "main.py"]
