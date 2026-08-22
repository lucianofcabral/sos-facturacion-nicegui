from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from src.domain.enums import EstadoCierre, OrigenCierre


class Periodo(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    nombre: str = Field(..., max_length=20)
    anio: int = Field(..., ge=2024, le=2100)
    mes: int = Field(..., ge=1, le=12)


class TipoServicio(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int | None = None
    rama: str = Field(..., max_length=25)
    nombre: str = Field(..., max_length=50)


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
