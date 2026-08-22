"""Entry point de la aplicación NiceGUI (SOS Facturación)."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from nicegui import app, ui

import src.ui.pages.home  # noqa: F401  (side-effect: registra la página '/')
from src.bootstrap import bootstrap

load_dotenv()

app.on_startup(bootstrap)

if __name__ in {"__main__", "__mp_main__"}:
    storage_secret = os.getenv("STORAGE_SECRET")
    if storage_secret is None:
        raise RuntimeError("STORAGE_SECRET no está configurada en el entorno (.env)")
    ui.run(
        title="SOS Facturación",
        port=8080,
        show=False,
        reload=True,
        dark=True,
        storage_secret=storage_secret,
    )
