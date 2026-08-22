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
