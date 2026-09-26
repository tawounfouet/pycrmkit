"""DRF exception bridge for stable PyCRMKit public errors."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from rest_framework import serializers, status
from rest_framework.exceptions import ErrorDetail, ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from pycrmkit.exceptions import (
    ConflictError,
    IntegrationError,
    NotFoundError,
    PyCRMKitError,
    RepositoryError,
    ValidationError,
)


if TYPE_CHECKING:
    class _SerializerBase(serializers.Serializer[Any]):
        pass
else:
    _SerializerBase = serializers.Serializer


class ErrorResponseSerializer(_SerializerBase):
    """Stable JSON representation of API-visible PyCRMKit errors."""

    code = serializers.CharField()
    message = serializers.CharField()
    context = serializers.DictField(required=False, default=dict)


_ERROR_STATUS_RULES: tuple[tuple[type[PyCRMKitError], int], ...] = (
    (ValidationError, status.HTTP_422_UNPROCESSABLE_ENTITY),
    (NotFoundError, status.HTTP_404_NOT_FOUND),
    (ConflictError, status.HTTP_409_CONFLICT),
    (RepositoryError, status.HTTP_500_INTERNAL_SERVER_ERROR),
    (IntegrationError, status.HTTP_502_BAD_GATEWAY),
    (PyCRMKitError, status.HTTP_500_INTERNAL_SERVER_ERROR),
)


def status_code_for_error(error: PyCRMKitError) -> int:
    """Map public PyCRMKit exceptions to stable HTTP status codes."""

    for error_type, status_code in _ERROR_STATUS_RULES:
        if isinstance(error, error_type):
            return status_code
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_safe(item) for item in value]
    return str(value)


def _error_payload(error: PyCRMKitError) -> dict[str, object]:
    return {
        "code": error.code,
        "message": error.message,
        "context": _json_safe(error.context),
    }


def _flatten_validation_errors(
    value: object,
    *,
    location: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    if isinstance(value, ErrorDetail):
        details.append(
            {
                "code": value.code,
                "location": list(location),
                "message": str(value),
            }
        )
        return details

    if isinstance(value, Mapping):
        for key, item in value.items():
            details.extend(
                _flatten_validation_errors(
                    item,
                    location=(*location, str(key)),
                )
            )
        return details

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, item in enumerate(value):
            details.extend(
                _flatten_validation_errors(
                    item,
                    location=(*location, str(index)),
                )
            )
        return details

    details.append(
        {
            "code": "invalid",
            "location": list(location),
            "message": str(value),
        }
    )
    return details


def pycrmkit_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response | None:
    """DRF EXCEPTION_HANDLER preserving PyCRMKit error codes and safe details."""

    if isinstance(exc, PyCRMKitError):
        return Response(
            _error_payload(exc),
            status=status_code_for_error(exc),
        )

    if isinstance(exc, DRFValidationError):
        response = drf_exception_handler(exc, context)
        if response is None:  # pragma: no cover - DRF contract guard
            return None
        return Response(
            {
                "code": "request.validation_error",
                "message": "request validation failed",
                "context": {
                    "errors": _flatten_validation_errors(response.data),
                },
            },
            status=response.status_code,
            headers=response.headers,
        )

    return drf_exception_handler(exc, context)


__all__ = [
    "ErrorResponseSerializer",
    "pycrmkit_exception_handler",
    "status_code_for_error",
]
