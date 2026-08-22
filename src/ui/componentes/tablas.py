"""Panel CRUD reutilizable: tabla + alta/edición/baja para una entidad."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from nicegui import ui

from src.ui.dialogos import open_form_dialog

OnSubmit = Callable[[dict, dict | None], Awaitable[None]]
OnDelete = Callable[[dict], Awaitable[None]]
GetInitial = Callable[[dict], dict]
Loader = Callable[[], Awaitable[list[dict]]]


class CrudPanel:
    def __init__(
        self,
        *,
        title: str,
        columns: list[dict],
        load: Loader,
        fields: list[dict],
        id_keys: list[str],
        on_submit: OnSubmit,
        on_delete: OnDelete | None = None,
        get_initial: GetInitial | None = None,
    ) -> None:
        self.title = title
        self.columns = columns
        self.load = load
        self.fields = fields
        self.id_keys = id_keys
        self.on_submit = on_submit
        self.on_delete = on_delete
        self.get_initial = get_initial
        self.table: ui.table | None = None

    async def render(self) -> None:
        rows = await self.load()
        with ui.column().classes("w-full gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(self.title).classes("text-h6")
                ui.button("Nuevo", on_click=self._open_create)
            self.table = ui.table(
                rows=rows, columns=self.columns, selection="single", pagination=10
            ).classes("w-full")
            with ui.row():
                if self.get_initial is not None:
                    ui.button("Editar", on_click=self._open_edit)
                if self.on_delete is not None:
                    ui.button("Eliminar", on_click=self._delete_selected)

    def _selected(self) -> dict | None:
        sel = self.table.selected if self.table is not None else None
        if isinstance(sel, list) and sel:
            return sel[0]
        return None

    async def _open_create(self) -> None:
        await open_form_dialog(
            title=f"Nuevo {self.title}",
            fields=self.fields,
            on_submit=self._submit_create,
        )

    async def _submit_create(self, values: dict) -> None:
        await self.on_submit(values, None)
        await self._refresh()

    async def _open_edit(self) -> None:
        row = self._selected()
        if row is None:
            ui.notify("Seleccioná una fila", type="warning")
            return
        initial = self.get_initial(row)
        await open_form_dialog(
            title=f"Editar {self.title}",
            fields=self.fields,
            initial=initial,
            on_submit=lambda v: self._submit_edit(v, row),
        )

    async def _submit_edit(self, values: dict, row: dict) -> None:
        await self.on_submit(values, row)
        await self._refresh()

    async def _delete_selected(self) -> None:
        if self.on_delete is None:
            return
        row = self._selected()
        if row is None:
            ui.notify("Seleccioná una fila", type="warning")
            return
        await self.on_delete(row)
        await self._refresh()

    async def _refresh(self) -> None:
        assert self.table is not None
        self.table.rows = await self.load()
        self.table.selected = []
        self.table.update()
