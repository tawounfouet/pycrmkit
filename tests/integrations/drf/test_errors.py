"""Domain and request error mapping tests for the DRF bridge."""

from __future__ import annotations

from rest_framework import serializers, status

from pycrmkit.exceptions import (
    ConflictError,
    IntegrationError,
    NotFoundError,
    PyCRMKitError,
    RepositoryError,
    ValidationError,
)
from pycrmkit.integrations.django.drf.errors import (
    pycrmkit_exception_handler,
    status_code_for_error,
)


def test_domain_error_status_mapping_matches_http_contract() -> None:
    assert status_code_for_error(ValidationError("bad")) == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert status_code_for_error(NotFoundError("missing")) == status.HTTP_404_NOT_FOUND
    assert status_code_for_error(ConflictError("conflict")) == status.HTTP_409_CONFLICT
    assert status_code_for_error(RepositoryError("db")) == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert status_code_for_error(IntegrationError("provider")) == status.HTTP_502_BAD_GATEWAY
    assert status_code_for_error(PyCRMKitError("base")) == status.HTTP_500_INTERNAL_SERVER_ERROR


def test_domain_error_preserves_code_message_and_safe_context() -> None:
    error = NotFoundError(
        "Contact not found",
        code="contact.not_found",
        context={"contact_id": "abc"},
    )

    response = pycrmkit_exception_handler(error, {})

    assert response is not None
    assert response.status_code == 404
    assert response.data == {
        "code": "contact.not_found",
        "message": "Contact not found",
        "context": {"contact_id": "abc"},
    }


def test_request_validation_is_normalized_without_input_echo() -> None:
    error = serializers.ValidationError(
        {
            "email": [
                serializers.ErrorDetail(
                    "Enter a valid email address.",
                    code="invalid",
                )
            ]
        }
    )

    response = pycrmkit_exception_handler(error, {})

    assert response is not None
    assert response.status_code == 400
    assert response.data["code"] == "request.validation_error"
    assert response.data["context"] == {
        "errors": [
            {
                "code": "invalid",
                "location": ["email", "0"],
                "message": "Enter a valid email address.",
            }
        ]
    }
    assert "submitted" not in str(response.data)
