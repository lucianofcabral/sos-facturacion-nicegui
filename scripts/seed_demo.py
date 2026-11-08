"""One-off CLI: seed fictitious demo data for local UI work (no real files).

Usage::

    DATABASE_URL=postgresql://... uv run scripts/seed_demo.py [--dry-run] [--reset]

Generates deterministic, clearly-synthetic data (tipos de servicio, periodos,
alícuotas, cápitas, servicios y cierres) through ``PostgresUoW`` in committed
phases, so every UI view renders without touching the real ``Panel.xlsm`` or the
``fapi`` service workbooks. Productor codes, license plates and service numbers
are fabricated.

Idempotency: aborts if any periodo inside the demo range already exists, unless
``--reset`` (which clears the demo tables first). The demo range is the last
``--meses`` months ending at 2025-12 (default 24: 2024-01 .. 2025-12).

Run the app afterwards with::

    DATABASE_URL=postgresql://... \
    ADMIN_NOMBRE=admin ADMIN_PASSWORD=admin1234 STORAGE_SECRET=dev-secret \
    RELOAD=false uv run main.py

Demo logins: ``admin/admin1234`` (ADMIN) y ``demo/demo1234`` (USUARIO).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from uuid import uuid4

import bcrypt

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# isort: off
from src.application.use_cases import cierre  # noqa: E402
from src.domain.enums import CategoriaServicio, RolUsuario  # noqa: E402
from src.domain.models.entities import (  # noqa: E402
    Alicuota,
    CapitaPeriodo,
    Periodo,
    Servicio,
    TipoServicio,
)
from src.domain.models.user import UsuarioApp  # noqa: E402
from src.infrastructure.adapters.uow import PostgresUoW  # noqa: E402
# isort: on

_MESES_ES = (
    "ENERO",
    "FEBRERO",
    "MARZO",
    "ABRIL",
    "MAYO",
    "JUNIO",
    "JULIO",
    "AGOSTO",
    "SEPTIEMBRE",
    "OCTUBRE",
    "NOVIEMBRE",
    "DICIEMBRE",
)

# Seeded tipos: (nombre, rama, codigo, categoria). Mirrors the real historical set.
_TIPOS = (
    ("Básico", "Automotores", "659", CategoriaServicio.BASICO),
    ("Básico 61", "Automotores", "61", CategoriaServicio.BASICO),
    ("Completo", "Automotores", "660", CategoriaServicio.COMPLETO),
    ("VIP", "Automotores", "658", CategoriaServicio.VIP),
    ("Rama 87", "Ramas Varias", "87", CategoriaServicio.RAMA_87),
    ("Rama 89", "Ramas Varias", "89", CategoriaServicio.RAMA_89),
    ("Rama 90", "Ramas Varias", "90", CategoriaServicio.RAMA_90),
)

# Códigos legacy que no deben aparecer como card de cápitas (sí como tipo,
# porque la resolución de import y el listado de servicios los necesitan).
_ALIAS_CODES = {"61"}

# Alícuota base: coeficientes y valor inicial por prestación (Automotores).
_COEFS = (0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060, 0.065)
_BASE_VALOR = {"Básico": 48787.0, "Completo": 65000.0, "VIP": 80000.0}

# Aumentos aplicados al cerrar ciertos periodos (key: (anio, mes), value: %).
_AUMENTOS = {
    (2024, 4): Decimal("8"),
    (2024, 10): Decimal("6"),
    (2025, 3): Decimal("7"),
    (2025, 7): Decimal("5"),
    (2025, 10): Decimal("4"),
}

# Conteos base por periodo. La síntesis lee cápitas de la tabla y servicios
# del ``servicio_conteos`` que derivamos de las filas realmente insertadas.
_SERV_BASE = {"Básico": 240, "Completo": 80, "VIP": 30}
_CAP_BASE = {
    "Básico": 320,
    "Completo": 105,
    "VIP": 40,
    "Rama 87": 25,
    "Rama 89": 30,
    "Rama 90": 35,
}

# Código legado de Básico (formato viejo): servicios con radio 61 que apuntan
# al tipo "Básico 61" (categoría básico). Solo se siembran en un mes puntual.
_LEGACY_61_BASE = 200
_LEGACY_61_CAP_BASE = 250
_MES_LEGACY_61 = (2025, 10)

# Códigos de productor ficticios (distribución sesgada para un "top productores"
# con forma, no una línea plana).
_PRODUCTORES = list(range(1000, 1040))
_PROD_WEIGHTS = list(range(len(_PRODUCTORES), 0, -1))

_LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_DIGITOS = "0123456789"


def _periodos(meses: int) -> list[tuple[int, int]]:
    """Last ``meses`` months ending at 2025-12, ascending."""
    out: list[tuple[int, int]] = []
    anio, mes = 2025, 12
    for _ in range(meses):
        out.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    out.reverse()
    return out


def _patente(rng: random.Random) -> str:
    return (
        "".join(rng.choice(_LETRAS) for _ in range(2))
        + "".join(rng.choice(_DIGITOS) for _ in range(3))
        + "".join(rng.choice(_LETRAS) for _ in range(2))
    )


def _redondear(valor: float) -> float:
    return float(Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _servicio(
    *,
    anio: int,
    mes: int,
    seq: int,
    rng: random.Random,
    periodo_id: int,
    tipo_servicio_id: int,
    codigo_radio: str,
) -> Servicio:
    return Servicio(
        nro_servicio=f"{anio}{mes:02d}{seq:07d}",
        codigo_radio=codigo_radio,
        fecha=date(anio, mes, rng.randint(1, 28)),
        dominio=_patente(rng),
        cod_productor=rng.choices(_PRODUCTORES, weights=_PROD_WEIGHTS, k=1)[0],
        periodo_id=periodo_id,
        tipo_servicio_id=tipo_servicio_id,
    )


def _plan(periodos: list[tuple[int, int]]) -> dict:
    # Estimación del volumen de servicios: suma de los conteos base con jitter.
    servicios = sum(sum(_SERV_BASE.values()) for _ in periodos)
    if _MES_LEGACY_61 in periodos:
        servicios += _LEGACY_61_BASE
    return {
        "tipos": len(_TIPOS),
        "periodos": len(periodos),
        "alicuotas_base": len(_COEFS) * 3,
        "capitas": len(_CAP_BASE) * len(periodos),
        "servicios_aprox": servicios,
        "cierres": len(periodos) - 2,  # los últimos 2 periodos quedan abiertos
        "usuarios": 2,
    }


async def _reset_demo(uow: PostgresUoW) -> None:
    """Clear demo tables in FK-safe order (script-only; no bulk-delete port)."""
    orden = (
        "DELETE FROM servicio",
        "DELETE FROM alicuota",
        "DELETE FROM capita_periodo",
        "DELETE FROM cierre",
        "DELETE FROM periodo",
        "DELETE FROM tipo_servicio",
        "DELETE FROM usuario",
    )
    async with uow._conn.cursor() as cur:  # one-off CLI: raw reset, no bulk-delete port
        for stmt in orden:
            await cur.execute(stmt)
    await uow.commit()


async def ejecutar_seed(
    periodos: list[tuple[int, int]], *, dry_run: bool = False, reset: bool = False
) -> dict:
    plan = _plan(periodos)
    if dry_run:
        return {"dry_run": True, **plan}

    async with PostgresUoW() as uow:
        if reset:
            await _reset_demo(uow)
        else:
            # Guard: abortar si el rango demo ya tiene periodos.
            anios = sorted({anio for anio, _ in periodos})
            for anio in anios:
                if await uow.periodos.get_by_anio(anio):
                    raise RuntimeError(
                        f"Ya existen periodos para anio={anio}. Corré con --reset "
                        "para regenerar (borra servicio/alicuota/capita/cierre/"
                        "periodo/tipo_servicio/usuario)."
                    )

        # Fase 1: tipos de servicio.
        tipo_ids: dict[str, int] = {}
        for nombre, rama, codigo, categoria in _TIPOS:
            t = await uow.tipos_servicio.add(
                TipoServicio(
                    rama=rama,
                    nombre=nombre,
                    codigo=codigo,
                    categoria=categoria,
                    es_alias=codigo in _ALIAS_CODES,
                )
            )
            assert t.id is not None
            tipo_ids[nombre] = t.id
        await uow.commit()

        # Fase 2: periodos contiguos.
        periodo_ids: dict[tuple[int, int], int] = {}
        for anio, mes in periodos:
            nombre = f"{_MESES_ES[mes - 1]} {anio}"
            p = await uow.periodos.add(Periodo(nombre=nombre, anio=anio, mes=mes))
            assert p.id is not None
            periodo_ids[(anio, mes)] = p.id
        await uow.commit()

        # Fase 3: alícuotas base del primer periodo (Automotores x3).
        primero = periodos[0]
        for nombre, base in _BASE_VALOR.items():
            for coef in _COEFS:
                await uow.alicuotas.add(
                    Alicuota(
                        periodo_id=periodo_ids[primero],
                        tipo_servicio_id=tipo_ids[nombre],
                        coeficiente=coef,
                        valor=_redondear(coef * base),
                    )
                )
        await uow.commit()

        # Fase 4: cápitas por periodo (6 tipos x periodo).
        for anio, mes in periodos:
            rng = random.Random(anio * 100 + mes)
            for nombre, base in _CAP_BASE.items():
                capitas = max(0, int(base * (0.9 + rng.random() * 0.2)))
                await uow.capitas_periodo.add(
                    CapitaPeriodo(
                        periodo_id=periodo_ids[(anio, mes)],
                        tipo_servicio_id=tipo_ids[nombre],
                        capitas=capitas,
                    )
                )
            # El código legado 61 aporta sus propias cápitas (la card queda
            # oculta por es_alias) para que el coef de uso lo cuente en básico.
            if (anio, mes) == _MES_LEGACY_61:
                capitas_61 = max(
                    0, int(_LEGACY_61_CAP_BASE * (0.9 + rng.random() * 0.2))
                )
                await uow.capitas_periodo.add(
                    CapitaPeriodo(
                        periodo_id=periodo_ids[(anio, mes)],
                        tipo_servicio_id=tipo_ids["Básico 61"],
                        capitas=capitas_61,
                    )
                )
        await uow.commit()

        # Fase 5: servicios ficticios por periodo (modo reemplazo = executemany).
        conteos_servicios: dict[tuple[int, int], dict[int, int]] = {}
        seq = 0
        for anio, mes in periodos:
            rng = random.Random(anio * 100 + mes)
            rows: list[Servicio] = []
            for nombre, base in _SERV_BASE.items():
                n = max(1, int(base * (0.85 + rng.random() * 0.3)))
                for _ in range(n):
                    seq += 1
                    rows.append(
                        _servicio(
                            anio=anio,
                            mes=mes,
                            seq=seq,
                            rng=rng,
                            periodo_id=periodo_ids[(anio, mes)],
                            tipo_servicio_id=tipo_ids[nombre],
                            codigo_radio=_codigo_de(nombre),
                        )
                    )
            # Código legado 61 (Básico viejo) solo en un mes puntual.
            if (anio, mes) == _MES_LEGACY_61:
                n_legacy = max(1, int(_LEGACY_61_BASE * (0.9 + rng.random() * 0.2)))
                for _ in range(n_legacy):
                    seq += 1
                    rows.append(
                        _servicio(
                            anio=anio,
                            mes=mes,
                            seq=seq,
                            rng=rng,
                            periodo_id=periodo_ids[(anio, mes)],
                            tipo_servicio_id=tipo_ids["Básico 61"],
                            codigo_radio="61",
                        )
                    )
            await uow.servicios.reemplazar_por_periodo(periodo_ids[(anio, mes)], rows)
            conteos_servicios[(anio, mes)] = {
                tid: sum(1 for s in rows if s.tipo_servicio_id == tid)
                for tid in {s.tipo_servicio_id for s in rows}
            }
        await uow.commit()

        # Fase 6: cierres oficiales en orden cronológico (últimos 2 quedan abiertos).
        abiertos = 2
        for i, (anio, mes) in enumerate(periodos[:-abiertos]):
            aumento = _AUMENTOS.get((anio, mes), Decimal("0"))
            await cierre.cerrar_periodo(
                uow,
                periodo_ids[(anio, mes)],
                aumento,
                servicio_conteos=conteos_servicios[(anio, mes)],
            )

        # Fase 7: usuarios demo (admin + demo), idempotente.
        for nombre, password, rol in (
            ("admin", "admin1234", RolUsuario.ADMIN),
            ("demo", "demo1234", RolUsuario.USUARIO),
        ):
            if await uow.usuarios.get_by_nombre(nombre) is None:
                await uow.usuarios.add(
                    UsuarioApp(
                        id=uuid4(),
                        nombre=nombre,
                        password_hash=_hash_password(password),
                        rol=rol,
                        email=None,
                        activo=True,
                    )
                )
        await uow.commit()

    return {"dry_run": False, **plan}


def _codigo_de(nombre: str) -> str:
    return {"Básico": "659", "Completo": "660", "VIP": "658"}[nombre]


def _resumen(resultado: dict) -> str:
    etiqueta = "DRY-RUN (plan)" if resultado["dry_run"] else "Seed demo completado"
    return "\n".join(
        [
            f"{etiqueta}:",
            f"  tipos: {resultado['tipos']}",
            f"  periodos: {resultado['periodos']}",
            f"  alicuotas base: {resultado['alicuotas_base']}",
            f"  capitas: {resultado['capitas']}",
            f"  servicios (aprox): {resultado['servicios_aprox']}",
            f"  cierres oficiales: {resultado['cierres']} (últimos 2 periodos abiertos)",
            "  usuarios: admin/admin1234 (ADMIN), demo/demo1234 (USUARIO)",
        ]
    )


async def _run(meses: int, dry_run: bool, reset: bool) -> None:
    periodos = _periodos(meses)
    resultado = await ejecutar_seed(periodos, dry_run=dry_run, reset=reset)
    print(_resumen(resultado))


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed demo con datos ficticios")
    parser.add_argument(
        "--meses",
        type=int,
        default=24,
        help="cantidad de meses a generar, terminando en 2025-12 (default: 24)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="planificar sin escribir nada",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="borrar las tablas demo antes de sembrar (regenerar)",
    )
    args = parser.parse_args()
    asyncio.run(_run(args.meses, args.dry_run, args.reset))


if __name__ == "__main__":
    main()
