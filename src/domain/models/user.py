from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import UUID4

from src.domain.enums import RolUsuario


class UsuarioApp(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID4
    nombre: str = Field(..., min_length=3)
    password_hash: str
    rol: RolUsuario
    email: str | None = None
    activo: bool
    creado_en: datetime | None = None
    actualizado_en: datetime | None = None
