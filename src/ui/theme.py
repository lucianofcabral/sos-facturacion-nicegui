"""Tema visual de la aplicación (colores de marca, tipografía y pulido CSS).

El tema se aplica una única vez desde ``main.py`` (``apply_theme``). La paleta
por categoría de tipo de servicio vive acá para que la vista de tipos (Phase 6)
derive el color de la ``categoria``, nunca del nombre.
"""

from __future__ import annotations

from nicegui import app, ui

PRIMARY = "#2563EB"
ACCENT = "#14B8A6"

LIGHT_BG = "#F5F7FA"
DARK_BG = "#121212"

# Color base por categoria de servicio (design.md). La clave coincide con el
# valor del enum ``CategoriaServicio`` para poder mapear ``categoria.value``.
CATEGORIA_COLORS: dict[str, str] = {
    "basico": "#3B82F6",
    "completo": "#14B8A6",
    "vip": "#A855F7",
    "rama_87": "#64748B",
    "rama_89": "#6B7280",
    "rama_90": "#94A3B8",
}

# Variante oscura (sufijo "-1") para mantener contraste en modo oscuro.
CATEGORIA_COLORS_DARK: dict[str, str] = {
    "basico": "#1E40AF",
    "completo": "#0F766E",
    "vip": "#7E22CE",
    "rama_87": "#475569",
    "rama_89": "#4B5563",
    "rama_90": "#64748B",
}


def _base_css() -> str:
    """CSS vars para fondo claro/oscuro y pulido de cards (radio + sombra)."""
    return (
        "<style>\n"
        ":root {\n"
        f"  --sos-bg: {LIGHT_BG};\n"
        "  --sos-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.08),"
        " 0 1px 2px rgba(0, 0, 0, 0.04);\n"
        "}\n"
        ".body--dark {\n"
        f"  --sos-bg: {DARK_BG};\n"
        "  --sos-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.45),"
        " 0 1px 2px rgba(0, 0, 0, 0.35);\n"
        "}\n"
        "body { background-color: var(--sos-bg); }\n"
        ".q-card {\n"
        "  border-radius: 0.75rem;\n"
        "  box-shadow: var(--sos-card-shadow);\n"
        "}\n"
        "</style>\n"
    )


def _category_css() -> str:
    """Generate ``.bg-<categoria>`` and its dark ``.bg-<categoria>-1`` variant."""
    rules: list[str] = []
    for categoria, color in CATEGORIA_COLORS.items():
        rules.append(f".bg-{categoria} {{ background-color: {color}; }}")
        dark = CATEGORIA_COLORS_DARK[categoria]
        rules.append(f".bg-{categoria}-1 {{ background-color: {dark}; }}")
    return "\n".join(rules) + "\n"


def apply_theme() -> None:
    """Apply global brand colors, fonts and CSS polish once at startup.

    ``app.colors`` mutates the Quasar brand config shared by every page (the
    ``ui.colors`` element is the per-page equivalent); ``add_head_html(shared=True)``
    injects the CSS variables and card polish into all pages.
    """
    app.colors(primary=PRIMARY, accent=ACCENT)
    ui.add_head_html(_base_css() + _category_css(), shared=True)
