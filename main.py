"""Entry point de la aplicación NiceGUI (SOS Facturación)."""

from __future__ import annotations

import os

from nicegui import app, ui

import src.ui.pages.home  # noqa: F401  (side-effect: registra la página '/')
from src.bootstrap import bootstrap

app.on_startup(bootstrap)

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="SOS Facturación",
        port=8080,
        show=False,
        reload=True,
        dark=True,
        # Habilita app.storage.user (persistente). En prod usar env STORAGE_SECRET.
        storage_secret=os.getenv("STORAGE_SECRET", "sos-dev-insecure-secret"),
    )
