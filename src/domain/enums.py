from enum import StrEnum


class RolUsuario(StrEnum):
    ADMIN = "admin"
    USUARIO = "usuario"


class CategoriaServicio(StrEnum):
    """Categoría de cálculo de un tipo de servicio (bucket de la síntesis).

    Identidad estable e independiente del ``nombre`` y del ``id``: las
    agrupaciones y cálculos (`computar_sintesis`) leen este campo, nunca
    strings mágicos del nombre.
    """

    BASICO = "basico"
    COMPLETO = "completo"
    VIP = "vip"
    RAMA_87 = "rama_87"
    RAMA_89 = "rama_89"
    RAMA_90 = "rama_90"


class EstadoCierre(StrEnum):
    OFICIAL = "oficial"
    NO_OFICIAL = "no_oficial"


class OrigenCierre(StrEnum):
    MANUAL = "manual"
    CASCADA = "cascada"
