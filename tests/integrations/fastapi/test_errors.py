"""FastAPI error-schema foundation qualification."""

from pycrmkit.exceptions import ValidationError
from pycrmkit.integrations.fastapi import ErrorResponse


def test_error_response_preserves_public_error_contract() -> None:
    error = ValidationError(
        "invalid input",
        code="contact.email.invalid",
        context={"field": "email"},
    )

    response = ErrorResponse.from_error(error)

    assert response.model_dump() == {
        "code": "contact.email.invalid",
        "message": "invalid input",
        "context": {"field": "email"},
    }
