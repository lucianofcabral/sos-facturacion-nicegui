"""Entry point de la aplicación NiceGUI (SOS Facturación)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from nicegui import app, ui

import src.ui.pages.home  # noqa: F401  (side-effect: registra la página '/')
from src.bootstrap import bootstrap
from src.ui.theme import apply_theme

load_dotenv()

apply_theme()
app.on_startup(bootstrap)

if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = os.getenv("STORAGE_SECRET")
    if storage_secret is None:
        raise RuntimeError("STORAGE_SECRET no está configurada en el entorno (.env)")
    ui.run(
        title="SOS Facturación",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8080")),
        show=False,
        reload=os.getenv("RELOAD", "true").lower() == "true",
        dark=True,
        storage_secret=storage_secret,
    )
