"""Diálogo genérico de alta/edición basado en una lista de campos.

Cada campo es un dict con:
  key, label, type ("text"|"number"|"password"|"select"|"date")
  type=="number": coerce ("int"|"float"), min, max, step
  type=="select": options -> lista fija, o callable (sync/async) que devuelve [(valor, etiqueta), ...]
"""

from __future__ import annotations

import inspect
from datetime import datetime

from nicegui import ui

FieldSpec = dict


async def open_form_dialog(
    *,
    title: str,
    fields: list[FieldSpec],
    on_submit,
    initial: dict | None = None,
    info: list[dict] | None = None,
    on_change=None,
    width: str = "w-[32rem]",
    submit_label: str = "Guardar",
    cancel_label: str = "Cancelar",
) -> None:
    initial = initial or {}
    info = info or []

    def _coerce(field: FieldSpec, raw):
        if raw in (None, ""):
            return None
        ftype = field.get("type", "text")
        if ftype == "number":
            return int(raw) if field.get("coerce") == "int" else float(raw)
        if ftype == "date":
            return datetime.strptime(raw, "%Y-%m-%d").date()
        return raw

    with ui.dialog() as dialog, ui.card().classes(width):
        ui.label(title).classes("text-h6")
        for item in info:
            ui.label(f"{item['label']}: {item['value']}").classes("text-caption")
        widgets: dict[str, object] = {}
        for f in fields:
            fk = f["key"]
            label = f["label"]
            ftype = f.get("type", "text")
            if ftype == "select":
                opts = f.get("options")
                if callable(opts):
                    opts = opts()
                if inspect.isawaitable(opts):
                    opts = await opts
                sel = ui.select(dict(opts or []), label=label)
                if fk in initial:
                    sel.value = initial[fk]
                widgets[fk] = sel
            elif ftype == "number":
                num = ui.number(
                    label=label,
                    min=f.get("min"),
                    max=f.get("max"),
                    step=f.get("step", 1),
                )
                if fk in initial:
                    num.value = initial[fk]
                widgets[fk] = num
            elif ftype == "date":
                d = ui.date(label=label)
                if fk in initial and initial[fk] is not None:
                    d.value = str(initial[fk])
                widgets[fk] = d
            elif ftype == "password":
                widgets[fk] = ui.input(
                    label=label, password=True, password_toggle_button=True
                )
            else:
                inp = ui.input(label=label)
                if fk in initial:
                    inp.value = initial[fk]
                widgets[fk] = inp

        warning = ui.label("").classes("text-caption text-negative")

        if on_change is not None:

            async def _revalidate(*_args) -> None:
                values = {
                    f["key"]: _coerce(f, widgets[f["key"]].value) for f in fields
                }
                result = on_change(values)
                if inspect.isawaitable(result):
                    result = await result
                warning.text = result or ""

            for f in fields:
                widgets[f["key"]].on_value_change(_revalidate)
            await _revalidate()

        with ui.row():
            ui.button(cancel_label, on_click=dialog.close)

            async def _submit() -> None:
                values = {f["key"]: _coerce(f, widgets[f["key"]].value) for f in fields}
                try:
                    await on_submit(values)
                    dialog.close()
                except Exception as exc:
                    ui.notify(f"Error: {exc}", type="negative")

            ui.button(submit_label, on_click=_submit)
    dialog.open()
