"""Typed HTTP error payload foundation for the FastAPI integration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pycrmkit.exceptions import PyCRMKitError


class ErrorResponse(BaseModel):
    """Framework-facing representation of one PyCRMKit error."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_error(cls, error: PyCRMKitError) -> ErrorResponse:
        """Convert a public PyCRMKit error without losing its stable error code."""

        return cls(
            code=error.code,
            message=error.message,
            context=dict(error.context),
        )


__all__ = ["ErrorResponse"]
