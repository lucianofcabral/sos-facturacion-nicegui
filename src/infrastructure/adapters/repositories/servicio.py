from __future__ import annotations

from datetime import date

from psycopg.rows import dict_row

from src.domain.enums import CategoriaServicio
from src.domain.models.entities import (
    ConteoCategoriaPeriodo,
    ConteoProductor,
    PaginaServicios,
    Servicio,
)
from src.domain.ports.repositories import ServicioRepository
from src.infrastructure.adapters.repositories._base import PostgresRepository


class ServicioRepositoryPg(PostgresRepository, ServicioRepository):
    table = "servicio"
    entity_type = Servicio
    key_fields = ("nro_servicio",)
    auto_fields = ()

    async def get(self, nro_servicio: str) -> Servicio | None:
        return await self._fetch_one(nro_servicio=nro_servicio)

    async def remove(self, nro_servicio: str) -> None:
        await self._delete(nro_servicio=nro_servicio)

    async def get_by_nro_servicio(self, nro_servicio: str) -> Servicio | None:
        return await self._fetch_one(nro_servicio=nro_servicio)

    async def get_by_fields(
        self,
        codigo_radio: str | None = None,
        fecha: object = None,
        dominio: str | None = None,
        cod_productor: int | None = None,
        periodo_id: int | None = None,
        tipo_servicio_id: int | None = None,
    ) -> list[Servicio]:
        filters = {
            "codigo_radio": codigo_radio,
            "fecha": fecha,
            "dominio": dominio,
            "cod_productor": cod_productor,
            "periodo_id": periodo_id,
            "tipo_servicio_id": tipo_servicio_id,
        }
        conditions: list[str] = []
        params: list[object] = []
        for column, value in filters.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                params.append(value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        sql = f"SELECT * FROM {self.table} {where}"
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()
        return [self._row_to_entity(r) for r in rows]

    async def search(
        self,
        periodo_id: int,
        texto: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
        page: int = 1,
        page_size: int = 15,
    ) -> PaginaServicios:
        conditions = ["periodo_id = %s"]
        params: list[object] = [periodo_id]
        if texto:
            term = f"%{texto}%"
            conditions.append(
                "(nro_servicio ILIKE %s OR codigo_radio ILIKE %s "
                "OR dominio ILIKE %s OR cod_productor::text ILIKE %s)"
            )
            params.extend([term, term, term, term])
        if desde is not None:
            conditions.append("fecha >= %s")
            params.append(desde)
        if hasta is not None:
            conditions.append("fecha <= %s")
            params.append(hasta)

        where = " AND ".join(conditions)
        offset = (page - 1) * page_size
        count_sql = f"SELECT COUNT(*)::int AS total FROM {self.table} WHERE {where}"
        page_sql = (
            f"SELECT * FROM {self.table} WHERE {where} "
            "ORDER BY nro_servicio LIMIT %s OFFSET %s"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(count_sql, params)
            row = await cur.fetchone()
            total = row["total"] if row is not None else 0
            await cur.execute(page_sql, [*params, page_size, offset])
            rows = await cur.fetchall()
        return PaginaServicios(rows=[self._row_to_entity(r) for r in rows], total=total)

    async def reemplazar_por_periodo(
        self, periodo_id: int, servicios: list[Servicio]
    ) -> None:
        """Atomically replace the period's services on the same connection.

        Mirrors ``AlicuotaRepositoryPg.reemplazar_por_periodo``: a raw DELETE
        scoped to ``periodo_id`` (so an empty set is legal) followed by a single
        ``executemany`` INSERT. Scope is by period because ``nro_servicio`` is
        globally unique.
        """
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"DELETE FROM {self.table} WHERE periodo_id = %s", (periodo_id,)
            )
            if servicios:
                rows = [
                    (
                        s.nro_servicio,
                        s.codigo_radio,
                        s.fecha,
                        s.dominio,
                        s.cod_productor,
                        s.periodo_id,
                        s.tipo_servicio_id,
                    )
                    for s in servicios
                ]
                await cur.executemany(
                    f"INSERT INTO {self.table} "
                    "(nro_servicio, codigo_radio, fecha, dominio, cod_productor, "
                    "periodo_id, tipo_servicio_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    rows,
                )

    async def conteo_por_categoria_periodo(self) -> list[ConteoCategoriaPeriodo]:
        sql = (
            "SELECT p.anio, p.mes, ts.categoria, COUNT(*)::int AS total "
            "FROM servicio s "
            "JOIN periodo p ON p.id = s.periodo_id "
            "JOIN tipo_servicio ts ON ts.id = s.tipo_servicio_id "
            "GROUP BY p.anio, p.mes, ts.categoria "
            "ORDER BY p.anio DESC, p.mes DESC, ts.categoria"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql)
            rows = await cur.fetchall()
        return [
            ConteoCategoriaPeriodo(
                anio=r["anio"],
                mes=r["mes"],
                categoria=CategoriaServicio(r["categoria"]),
                total=r["total"],
            )
            for r in rows
        ]

    async def top_productores(self, limite: int = 10) -> list[ConteoProductor]:
        sql = (
            "SELECT cod_productor, COUNT(*)::int AS total "
            "FROM servicio "
            "GROUP BY cod_productor "
            "ORDER BY COUNT(*) DESC, cod_productor "
            "LIMIT %s"
        )
        async with self._conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(sql, (limite,))
            rows = await cur.fetchall()
        return [
            ConteoProductor(cod_productor=r["cod_productor"], total=r["total"])
            for r in rows
        ]
