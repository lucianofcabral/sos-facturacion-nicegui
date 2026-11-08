"""Campos y validación de los diálogos de tipo de servicio."""

from __future__ import annotations

CATEGORIA_OPTS = [
    ("basico", "Básico"),
    ("completo", "Completo"),
    ("vip", "VIP"),
    ("rama_87", "Rama 87"),
    ("rama_89", "Rama 89"),
    ("rama_90", "Rama 90"),
]

TIPO_SERVICIO_FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "rama", "label": "Rama", "type": "text"},
    {"key": "codigo", "label": "Código (único)", "type": "text"},
    {
        "key": "categoria",
        "label": "Categoría",
        "type": "select",
        "options": CATEGORIA_OPTS,
    },
    {"key": "es_alias", "label": "Es alias (código legado)", "type": "bool"},
]


def validar_tipo_servicio(values: dict) -> str | None:
    """Advertencia de validación para el formulario (``None`` = válido).

    Refleja las restricciones de ``TipoServicio`` (campos obligatorios y
    longitudes máximas) para dar pistas antes de enviar.
    """
    rama = str(values.get("rama") or "").strip()
    nombre = str(values.get("nombre") or "").strip()
    codigo = str(values.get("codigo") or "").strip()
    categoria = values.get("categoria")
    if not rama or not nombre or not codigo or not categoria:
        return "Rama, nombre, código y categoría son obligatorios."
    if len(rama) > 25:
        return "La rama no puede superar 25 caracteres."
    if len(nombre) > 50:
        return "El nombre no puede superar 50 caracteres."
    if len(codigo) > 10:
        return "El código no puede superar 10 caracteres."
    return None
