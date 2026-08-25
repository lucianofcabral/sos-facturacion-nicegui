from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import CategoriaServicio, EstadoCierre, OrigenCierre


class Periodo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    nombre: str = Field(..., max_length=20)
    anio: int = Field(..., ge=2014, le=2100)
    mes: int = Field(..., ge=1, le=12)
    hojas_entrada: dict | None = None


class PeriodoConEstado(BaseModel):
    """Read model: periodo + estado de cierre + total + cuadro (not persisted)."""

    model_config = ConfigDict(frozen=True)

    id: int
    nombre: str
    anio: int
    mes: int
    cerrado: bool
    total: Decimal | None = None
    cuadro: dict | None = None


class TipoServicio(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    rama: str = Field(..., max_length=25)
    nombre: str = Field(..., max_length=50)
    codigo: str = Field(..., max_length=10)
    categoria: CategoriaServicio = Field(...)


class MetricasTipoServicio(BaseModel):
    """Read model: derived metrics for a tipo de servicio (not persisted)."""

    model_config = ConfigDict(frozen=True)

    servicios_asociados: int = 0
    ciclos: int = 0
    primer_ciclo: str | None = None
    ultimo_ciclo: str | None = None


class Alicuota(BaseModel):
    model_config = ConfigDict(frozen=True)

    periodo_id: int = Field(...)
    tipo_servicio_id: int = Field(...)
    coeficiente: float = Field(..., gt=0.0, lt=1.0)
    valor: float = Field(..., gt=0.0)

    periodo: Periodo | None = None
    tipo_servicio: TipoServicio | None = None


class Servicio(BaseModel):
    model_config = ConfigDict(frozen=True)

    nro_servicio: str = Field(..., max_length=28)
    codigo_radio: str | None = Field(default=None, max_length=6)
    fecha: date = Field(...)
    dominio: str | None = Field(default=None, max_length=12)
    cod_productor: int = Field(...)
    periodo_id: int = Field(...)
    tipo_servicio_id: int = Field(...)

    periodo: Periodo | None = None
    tipo_servicio: TipoServicio | None = None


class CapitaPeriodo(BaseModel):
    model_config = ConfigDict(frozen=True)

    periodo_id: int = Field(...)
    tipo_servicio_id: int = Field(...)
    capitas: int = Field(..., ge=0)

    periodo: Periodo | None = None
    tipo_servicio: TipoServicio | None = None


class CapitaPeriodoConTipo(BaseModel):
    """Read model: tipo + su capita para un periodo (not persisted)."""

    model_config = ConfigDict(frozen=True)

    tipo_servicio_id: int
    tipo_nombre: str
    capitas: int | None = None


class Cierre(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    periodo_id: int = Field(...)
    version: int = Field(..., ge=1)
    estado: EstadoCierre = Field(...)
    origen: OrigenCierre = Field(...)
    motivo: str | None = None
    aumento: Decimal = Field(..., gt=-100)
    snapshot: dict | None = None
    creado_en: datetime | None = None


class SintesisPeriodo(BaseModel):
    """Read-model for the snapshot síntesis cuadro (not persisted).

    Frozen like the rest of the domain. Decimal for coefficients, values and
    total (spec requires ROUND_HALF_UP to 2dp); int for capitas and service
    counts. Per-tipo coefficients are kept as informational values while the
    global ``coef_uso`` drives the bracket lookup.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    aumento: Decimal

    capitas_total: int = 0
    capitas_basico: int = 0
    capitas_completo: int = 0
    capitas_vip: int = 0
    capitas_rama_87: int = 0
    capitas_rama_89: int = 0
    capitas_rama_90: int = 0

    servicios_total: int = 0
    servicios_basico: int = 0
    servicios_completo: int = 0
    servicios_vip: int = 0

    coef_uso: Decimal = Decimal("0")
    coef_uso_basico: Decimal = Decimal("0")
    coef_uso_completo: Decimal = Decimal("0")
    coef_uso_vip: Decimal = Decimal("0")
    coef_indice: Decimal = Decimal("0")

    valor_basico: Decimal = Decimal("0")
    valor_completo: Decimal = Decimal("0")
    valor_vip: Decimal = Decimal("0")

    total: Decimal = Decimal("0")
