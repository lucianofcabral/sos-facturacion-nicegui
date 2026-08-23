"""Campos de los diálogos de tipo de servicio."""

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
    {"key": "rama", "label": "Rama", "type": "text"},
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "codigo", "label": "Código", "type": "text"},
    {
        "key": "categoria",
        "label": "Categoría",
        "type": "select",
        "options": CATEGORIA_OPTS,
    },
]
