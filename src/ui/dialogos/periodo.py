"""Campos de los diálogos de periodo y cierre."""

from __future__ import annotations

PERIODO_FIELDS = [
    {"key": "nombre", "label": "Nombre", "type": "text"},
    {"key": "anio", "label": "Año", "type": "number", "coerce": "int", "min": 2014, "max": 2100},
    {"key": "mes", "label": "Mes", "type": "number", "coerce": "int", "min": 1, "max": 12},
]

CIERRE_FIELDS = [
    {"key": "aumento", "label": "Aumento (%)", "type": "number", "coerce": "float", "min": -99.99, "step": 0.01},
    {"key": "motivo", "label": "Motivo", "type": "text"},
]
