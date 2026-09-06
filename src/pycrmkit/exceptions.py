"""Public PyCRMKit exception hierarchy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar


class PyCRMKitError(Exception):
    """Base class for typed, machine-readable PyCRMKit errors."""

    default_code: ClassVar[str] = "pycrmkit.error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.context = dict(context or {})

    def as_dict(self) -> dict[str, object]:
        """Return a structured representation suitable for API/error adapters."""

        return {
            "code": self.code,
            "message": self.message,
            "context": dict(self.context),
        }


class ValidationError(PyCRMKitError):
    """Domain or input validation failed."""

    default_code = "validation.error"


class NotFoundError(PyCRMKitError):
    """A requested domain resource does not exist."""

    default_code = "resource.not_found"


class ConflictError(PyCRMKitError):
    """The requested operation conflicts with current domain state."""

    default_code = "resource.conflict"


class DuplicateError(ConflictError):
    """A uniqueness/idempotency rule detected a duplicate."""

    default_code = "resource.duplicate"


class InvalidStateError(ConflictError):
    """A domain state transition or mutation is not allowed."""

    default_code = "state.invalid"


class RepositoryError(PyCRMKitError):
    """Persistence adapter or repository operation failed."""

    default_code = "repository.error"


class IntegrationError(PyCRMKitError):
    """An external integration or provider operation failed."""

    default_code = "integration.error"


__all__ = [
    "ConflictError",
    "DuplicateError",
    "IntegrationError",
    "InvalidStateError",
    "NotFoundError",
    "PyCRMKitError",
    "RepositoryError",
    "ValidationError",
]
