"""Tema visual de la aplicación (colores de marca, tipografía y pulido CSS).

El tema se aplica una única vez desde ``main.py`` (``apply_theme``). La paleta
por categoría de tipo de servicio vive acá para que la vista de tipos (Phase 6)
derive el color de la ``categoria``, nunca del nombre.
"""

from __future__ import annotations

from nicegui import app, ui

PRIMARY = "#DC2626"
ACCENT = "#E11D48"

LIGHT_BG = "#F5F7FA"
DARK_BG = "#121212"

# Color base por categoria de servicio (design.md). La clave coincide con el
# valor del enum ``CategoriaServicio`` para poder mapear ``categoria.value``.
# Paleta roja monocromática (escala de Tailwind red) con tonos distinguibles:
# los automotores (basico/completo/vip) van de red-600 a red-900 y las ramas
# (87/89/90) de red-500 a red-300, para que se lean como una única familia.
CATEGORIA_COLORS: dict[str, str] = {
    "basico": "#DC2626",  # red-600
    "completo": "#B91C1C",  # red-700
    "vip": "#7F1D1D",  # red-900
    "rama_87": "#EF4444",  # red-500
    "rama_89": "#F87171",  # red-400
    "rama_90": "#FCA5A5",  # red-300
}

# Variante oscura (sufijo "-1") para mantener contraste en modo oscuro: un
# paso más oscura que su par clara, conservando la misma escala roja.
CATEGORIA_COLORS_DARK: dict[str, str] = {
    "basico": "#7F1D1D",  # red-900
    "completo": "#991B1B",  # red-800
    "vip": "#450A0A",  # red-950
    "rama_87": "#DC2626",  # red-600
    "rama_89": "#EF4444",  # red-500
    "rama_90": "#F87171",  # red-400
}


def _base_css() -> str:
    """CSS vars para fondo claro/oscuro y pulido de cards (radio + sombra).

    NiceGUI renderiza ``ui.card()`` como el tag ``q-card`` con clase
    ``nicegui-card`` (no con clase ``q-card``): el selector tiene que ser el tag
    ``q-card`` para que el borde/radio/sombra se apliquen. NiceGUI además anula
    por defecto ``box-shadow`` y ``border-radius`` del card, así que acá los
    restauramos junto con un fondo y un borde visibles para que el encabezado y
    las cards no se confundan con el fondo de la página.
    """
    return (
        "<style>\n"
        ":root {\n"
        f"  --sos-bg: {LIGHT_BG};\n"
        "  --sos-card-bg: #FFFFFF;\n"
        "  --sos-card-border: rgba(0, 0, 0, 0.08);\n"
        "  --sos-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.10),"
        " 0 1px 2px rgba(0, 0, 0, 0.06);\n"
        "}\n"
        ".body--dark {\n"
        f"  --sos-bg: {DARK_BG};\n"
        "  --sos-card-bg: #1E1E1E;\n"
        "  --sos-card-border: rgba(255, 255, 255, 0.12);\n"
        "  --sos-card-shadow: 0 1px 3px rgba(0, 0, 0, 0.45),"
        " 0 1px 2px rgba(0, 0, 0, 0.35);\n"
        "}\n"
        "body { background-color: var(--sos-bg); }\n"
        "q-card {\n"
        "  background: var(--sos-card-bg);\n"
        "  border: 1px solid var(--sos-card-border);\n"
        "  border-radius: 0.75rem;\n"
        "  box-shadow: var(--sos-card-shadow);\n"
        "}\n"
        # Layout del panel de detalle: columna principal + barra lateral fija.
        # Sin media queries de Tailwind (el build es precompilado): colapsa a una
        # sola columna por debajo de 1180px.
        ".sos-panel-grid {\n"
        "  display: grid;\n"
        "  grid-template-columns: minmax(0, 1fr) 336px;\n"
        "  gap: 18px;\n"
        "  align-items: start;\n"
        "}\n"
        ".sos-panel-side { position: sticky; top: 16px; }\n"
        # Cápitas: automotores y ramas varias en dos columnas paralelas,
        # centradas en la card y con separación amplia entre sí. Cada bloque
        # tiene ancho máximo propio para no estirarse en pantallas anchas.
        ".sos-cap-grid {\n"
        "  display: grid;\n"
        "  grid-template-columns: repeat(2, minmax(0, 420px));\n"
        "  justify-content: center;\n"
        "  column-gap: 56px;\n"
        "  row-gap: 20px;\n"
        "  align-items: start;\n"
        "}\n"
        ".sos-group-title { font-size: 11px; text-transform: uppercase;\n"
        "  letter-spacing: 0.06em; opacity: 0.6; font-weight: 700; }\n"
        "@media (max-width: 1180px) {\n"
        "  .sos-panel-grid { grid-template-columns: minmax(0, 1fr); }\n"
        "  .sos-panel-side { position: static; }\n"
        "}\n"
        "@media (max-width: 900px) {\n"
        "  .sos-cap-grid { grid-template-columns: minmax(0, 420px); }\n"
        "}\n"
        # Tabla densa editable (cápitas) y utilidades de números/lectores.
        ".sos-table { width: 100%; border-collapse: collapse; }\n"
        ".sos-table th { font-size: 11px; text-transform: uppercase;\n"
        "  letter-spacing: 0.06em; opacity: 0.6; font-weight: 700;\n"
        "  text-align: left; padding: 0 8px 7px; }\n"
        ".sos-table td { padding: 5px 8px;\n"
        "  border-top: 1px solid var(--sos-card-border); }\n"
        ".sos-table .sos-group td { border-top: none; padding-top: 14px;\n"
        "  font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;\n"
        "  opacity: 0.6; font-weight: 700; }\n"
        ".sos-table tfoot td { border-top: 1px solid var(--sos-card-border);\n"
        "  font-weight: 650; padding-top: 10px; }\n"
        ".sos-num { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas,\n"
        "  monospace; font-variant-numeric: tabular-nums; white-space: nowrap; }\n"
        ".sos-sr { position: absolute; width: 1px; height: 1px; overflow: hidden;\n"
        "  clip: rect(0 0 0 0); white-space: nowrap; }\n"
        ".sos-dot { display: inline-block; width: 8px; height: 8px;\n"
        "  border-radius: 999px; margin-right: 8px; }\n"
        "</style>\n"
    )


def _category_css() -> str:
    """Generate ``.bg-<categoria>`` and its dark ``.bg-<categoria>-1`` variant."""
    rules: list[str] = []
    for categoria, color in CATEGORIA_COLORS.items():
        rules.append(f".bg-{categoria} {{ background-color: {color}; }}")
        dark = CATEGORIA_COLORS_DARK[categoria]
        rules.append(f".bg-{categoria}-1 {{ background-color: {dark}; }}")
    return "<style>\n" + "\n".join(rules) + "\n</style>\n"


def apply_theme() -> None:
    """Apply global brand colors, fonts and CSS polish once at startup.

    ``app.colors`` mutates the Quasar brand config shared by every page (the
    ``ui.colors`` element is the per-page equivalent); ``add_head_html(shared=True)``
    injects the CSS variables and card polish into all pages.
    """
    app.colors(primary=PRIMARY, accent=ACCENT)
    ui.add_head_html(_base_css() + _category_css(), shared=True)
