"""HTTP error mapping, handlers and OpenAPI error documentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from pycrmkit.exceptions import (
    ConflictError,
    IntegrationError,
    NotFoundError,
    PyCRMKitError,
    RepositoryError,
    ValidationError,
)


class ErrorResponse(BaseModel):
    """Stable HTTP representation of one API-visible error."""

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


_ERROR_STATUS_RULES: tuple[tuple[type[PyCRMKitError], int], ...] = (
    (ValidationError, status.HTTP_422_UNPROCESSABLE_CONTENT),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (RepositoryError, status.HTTP_500_INTERNAL_SERVER_ERROR),
    (IntegrationError, status.HTTP_502_BAD_GATEWAY),
    (PyCRMKitError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def status_code_for_error(error: PyCRMKitError) -> int:
    """Return the stable HTTP status associated with a public domain error."""

    for error_type, status_code in _ERROR_STATUS_RULES:
        if isinstance(error, error_type):
            return status_code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _request_validation_context(
    errors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return JSON-safe validation details without echoing submitted input."""

    details: list[dict[str, Any]] = []
    for error in errors:
        details.append(
            {
                "type": str(error.get("type", "validation_error")),
                "location": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "invalid request")),
            }
        )
    return {"errors": details}


async def pycrmkit_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Render PyCRMKit domain errors using the stable ErrorResponse contract."""

    del request
    if not isinstance(exc, PyCRMKitError):  # pragma: no cover - registration guard
        raise exc
    payload = ErrorResponse.from_error(exc)
    return JSONResponse(
        status_code=status_code_for_error(exc),
        content=payload.model_dump(mode="json"),
    )


async def request_validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Normalize FastAPI request validation failures to ErrorResponse."""

    del request
    if not isinstance(exc, RequestValidationError):  # pragma: no cover
        raise exc
    payload = ErrorResponse(
        code="request.validation_error",
        message="request validation failed",
        context=_request_validation_context(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=payload.model_dump(mode="json"),
    )


def install_error_handlers(app: FastAPI) -> FastAPI:
    """Register PyCRMKit and request-validation handlers on an application."""

    app.add_exception_handler(PyCRMKitError, pycrmkit_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        request_validation_exception_handler,
    )
    return app


_ERROR_RESPONSE_EXAMPLES: dict[int, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "resource_not_found": {
            "summary": "Resource not found",
            "value": {
                "code": "resource.not_found",
                "message": "resource not found",
                "context": {},
            },
        }
    },
    status.HTTP_409_CONFLICT: {
        "domain_conflict": {
            "summary": "Domain conflict",
            "value": {
                "code": "resource.conflict",
                "message": "operation conflicts with current state",
                "context": {},
            },
        }
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "domain_validation": {
            "summary": "Domain validation failed",
            "value": {
                "code": "validation.error",
                "message": "invalid input",
                "context": {},
            },
        },
        "request_validation": {
            "summary": "Request validation failed",
            "value": {
                "code": "request.validation_error",
                "message": "request validation failed",
                "context": {
                    "errors": [
                        {
                            "type": "missing",
                            "location": ["body", "field"],
                            "message": "Field required",
                        }
                    ]
                },
            },
        },
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "repository_failure": {
            "summary": "Persistence failure",
            "value": {
                "code": "repository.error",
                "message": "repository operation failed",
                "context": {},
            },
        }
    },
    status.HTTP_502_BAD_GATEWAY: {
        "integration_failure": {
            "summary": "External integration failure",
            "value": {
                "code": "integration.error",
                "message": "external integration failed",
                "context": {},
            },
        }
    },
}

_ERROR_RESPONSE_DESCRIPTIONS: dict[int, str] = {
    status.HTTP_404_NOT_FOUND: "The requested CRM resource was not found.",
    status.HTTP_409_CONFLICT: "The operation conflicts with current domain state.",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "Request or domain validation failed.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "A PyCRMKit repository operation failed.",
    status.HTTP_502_BAD_GATEWAY: "An external integration used by PyCRMKit failed.",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """Build FastAPI response metadata with ErrorResponse and examples."""

    responses: dict[int | str, dict[str, Any]] = {}
    for status_code in status_codes:
        try:
            examples = _ERROR_RESPONSE_EXAMPLES[status_code]
            description = _ERROR_RESPONSE_DESCRIPTIONS[status_code]
        except KeyError as exc:
            raise ValueError(f"unsupported documented error status: {status_code}") from exc
        responses[status_code] = {
            "model": ErrorResponse,
            "description": description,
            "content": {
                "application/json": {
                    "examples": examples,
                }
            },
        }
    return responses


CREATE_ERROR_RESPONSES = error_responses(409, 422, 500)
LIST_ERROR_RESPONSES = error_responses(422, 500)
READ_ERROR_RESPONSES = error_responses(404, 422, 500)
MUTATION_ERROR_RESPONSES = error_responses(404, 409, 422, 500)


__all__ = [
    "CREATE_ERROR_RESPONSES",
    "ErrorResponse",
    "LIST_ERROR_RESPONSES",
    "MUTATION_ERROR_RESPONSES",
    "READ_ERROR_RESPONSES",
    "error_responses",
    "install_error_handlers",
    "pycrmkit_exception_handler",
    "request_validation_exception_handler",
    "status_code_for_error",
]
