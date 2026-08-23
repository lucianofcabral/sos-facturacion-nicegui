"""Creation DTOs (input boundary) for domain entities.

Every DTO here omits generated identifiers and uses flat foreign-key ids for
the composite entities, keeping creation independent of nested reads. Fields
mirror the NOT NULL constraints of the database schema.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from src.domain.enums import RolUsuario


class CreatePeriodo(BaseModel):
    nombre: str = Field(..., max_length=20)
    anio: int = Field(..., ge=2024, le=2100)
    mes: int = Field(..., ge=1, le=12)


class CreateTipoServicio(BaseModel):
    rama: str = Field(..., max_length=25)
    nombre: str = Field(..., max_length=50)
    codigo: str = Field(..., max_length=10)


class CreateAlicuota(BaseModel):
    periodo_id: int
    tipo_servicio_id: int
    coeficiente: float = Field(..., gt=0.0, lt=1.0)
    valor: float = Field(..., gt=0.0)


class CreateServicio(BaseModel):
    nro_servicio: str = Field(..., max_length=28)
    codigo_radio: str | None = Field(default=None, max_length=6)
    fecha: date = Field(...)
    dominio: str | None = Field(default=None, max_length=12)
    cod_productor: int = Field(...)
    periodo_id: int = Field(...)
    tipo_servicio_id: int = Field(...)


class CreateCapitaPeriodo(BaseModel):
    periodo_id: int
    tipo_servicio_id: int
    capitas: int = Field(..., ge=0)


class UsuarioCreate(BaseModel):
    nombre: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    rol: RolUsuario = RolUsuario.USUARIO
    email: str | None = None


class CreateCierre(BaseModel):
    aumento: Decimal = Field(..., gt=-100)
    motivo: str | None = None
