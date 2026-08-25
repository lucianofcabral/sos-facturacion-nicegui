"""Formatos de presentación reutilizables (moneda y números)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def format_ars(value) -> str:
    """Formatea un importe como moneda argentina: ``$ 1.234.567,89``.

    Miles con punto, decimales con coma y prefijo ``$ ``. Devuelve ``—`` cuando
    el valor no es numérico o es ``None`` (por ejemplo, un periodo abierto sin
    cierre oficial).
    """
    if value is None or value == "":
        return "—"
    try:
        monto = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return "—"
    texto = f"{monto:,.2f}"
    # Convierte ``1,234,567.89`` en ``1.234.567,89`` intercambiando separadores.
    texto = texto.replace(",", "\u0000").replace(".", ",").replace("\u0000", ".")
    return f"$ {texto}"


def format_int(value) -> str:
    """Formatea un entero con separador de miles (coma); ``—`` si no es numérico.

    Espejo de ``_fmt_entero`` de la vista de periodos, promovido a helper
    reutilizable. Miles con coma para mantenerse consistente con el resto de la
    UI (moneda aparte usa formato es-AR con punto).
    """
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "—"
