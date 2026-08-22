from enum import StrEnum


class RolUsuario(StrEnum):
    ADMIN = "admin"
    USUARIO = "usuario"


class EstadoCierre(StrEnum):
    OFICIAL = "oficial"
    NO_OFICIAL = "no_oficial"


class OrigenCierre(StrEnum):
    MANUAL = "manual"
    CASCADA = "cascada"
