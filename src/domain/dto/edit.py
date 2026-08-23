"""Update DTOs (partial input boundary) for domain entities.

All fields are optional so a caller can patch a subset of attributes. The
entity id is supplied separately by the use case, not inside the DTO.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from src.domain.enums import RolUsuario


class EditPeriodo(BaseModel):
    nombre: str | None = None
    anio: int | None = Field(default=None, ge=2024, le=2100)
    mes: int | None = Field(default=None, ge=1, le=12)


class EditTipoServicio(BaseModel):
    rama: str | None = Field(default=None, max_length=25)
    nombre: str | None = Field(default=None, max_length=50)
    codigo: str | None = Field(default=None, max_length=10)


class EditAlicuota(BaseModel):
    periodo_id: int
    tipo_servicio_id: int
    coeficiente: float = Field(..., gt=0.0, lt=1.0)
    valor: float = Field(gt=0.0)


class EditServicio(BaseModel):
    nro_servicio: str = Field(..., max_length=28)
    codigo_radio: str | None = Field(default=None, max_length=6)
    fecha: date | None = None
    dominio: str | None = Field(default=None, max_length=12)
    cod_productor: int | None = None
    periodo_id: int | None = None
    tipo_servicio_id: int | None = None


class EditCapitaPeriodo(BaseModel):
    periodo_id: int
    tipo_servicio_id: int
    capitas: int | None = Field(default=None, gt=0)


class UsuarioEdit(BaseModel):
    nombre: str | None = Field(default=None, min_length=3)
    email: str | None = None
    rol: RolUsuario | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=8)
