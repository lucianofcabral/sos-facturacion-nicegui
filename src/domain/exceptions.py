"""Domain and repository exceptions.

These live in the domain layer so the application and adapters can depend on
stable error types without importing infrastructure details.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every error raised by the domain layer."""


class RepositoryError(DomainError):
    """Base class for errors raised by repository implementations."""


class EntityNotFoundError(RepositoryError):
    """Raised when no entity exists for a given identifier."""

    def __init__(self, entity: str, id: int | str) -> None:
        self.entity = entity
        self.id = id
        super().__init__(f"{entity} with id={id!r} was not found")


class DuplicateKeyError(RepositoryError):
    """Raised on a unique-constraint violation."""

    def __init__(self, field: str, value: object = None) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Duplicate value for field {field!r}: {value!r}")


class ConstraintViolationError(RepositoryError):
    """Raised on a foreign-key or other integrity violation."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ConcurrencyError(RepositoryError):
    """Raised when an optimistic-lock / version check fails."""

    def __init__(self, entity: str, id: int | str) -> None:
        self.entity = entity
        self.id = id
        super().__init__(f"Concurrent modification detected for {entity} id={id!r}")


class AuthorizationError(DomainError):
    """Raised when an actor lacks permission for an operation."""

    def __init__(self, message: str = "Operation not permitted") -> None:
        super().__init__(message)


class PeriodoAlreadyClosedError(DomainError):
    """Raised when a period already has an official cierre."""

    def __init__(self, periodo_id: int) -> None:
        self.periodo_id = periodo_id
        super().__init__(f"Periodo id={periodo_id!r} already has an official cierre")


class PeriodoNotClosedError(DomainError):
    """Raised when a period has no official cierre to re-close or demote."""

    def __init__(self, periodo_id: int) -> None:
        self.periodo_id = periodo_id
        super().__init__(f"Periodo id={periodo_id!r} has no official cierre")


class RecalculoInvalidoError(DomainError):
    """Raised when recalculation would produce a valor <= 0 (after rounding)."""

    def __init__(self, tipo_servicio_id: int | None = None) -> None:
        self.tipo_servicio_id = tipo_servicio_id
        if tipo_servicio_id is not None:
            super().__init__(
                f"Recalculo produjo valor <= 0 para tipo_servicio_id={tipo_servicio_id!r}"
            )
        else:
            super().__init__("Recalculo produjo valor <= 0")


class AlicuotaProgresionError(DomainError):
    """Raised when an alicuota valor breaks the monotonic progression.

    ``inferior`` and ``superior`` are ``(coeficiente, valor)`` tuples describing
    the bracket where the violation happened, so the UI can show where the
    alicuota would sit.
    """

    def __init__(
        self,
        tipo_servicio_id: int,
        *,
        inferior: tuple[float, float],
        superior: tuple[float, float],
    ) -> None:
        self.tipo_servicio_id = tipo_servicio_id
        self.inferior = inferior
        self.superior = superior
        super().__init__(
            f"La alícuota rompe la progresión: valor {superior[1]} "
            f"(coef {superior[0]}) no puede ser inferior a {inferior[1]} "
            f"(coef {inferior[0]})"
        )


class ImportServiciosError(DomainError):
    """Raised when the Excel service import cannot proceed safely.

    Covers mixed months in sheet 0, missing/unknown columns, empty required
    cells and unmapped ``codigo_radio``. Always raised before any write so the
    import leaves the database untouched.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class PanelHistoricoError(DomainError):
    """Raised when the historical Panel parser cannot proceed safely.

    Covers missing sheets, missing/unknown columns and unparseable cells. Always
    raised before any write so a failed seed leaves the database untouched.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
