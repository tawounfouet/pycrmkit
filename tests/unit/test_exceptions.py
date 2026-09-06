from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    IntegrationError,
    InvalidStateError,
    NotFoundError,
    PyCRMKitError,
    RepositoryError,
    ValidationError,
)


def test_error_exposes_machine_readable_code_and_context() -> None:
    error = NotFoundError(
        "Contact not found",
        code="contact.not_found",
        context={"contact_id": "c-123"},
    )

    assert str(error) == "Contact not found"
    assert error.code == "contact.not_found"
    assert error.context == {"contact_id": "c-123"}
    assert error.as_dict() == {
        "code": "contact.not_found",
        "message": "Contact not found",
        "context": {"contact_id": "c-123"},
    }


def test_error_hierarchy_and_default_codes() -> None:
    assert ValidationError("invalid").code == "validation.error"
    assert NotFoundError("missing").code == "resource.not_found"
    assert ConflictError("conflict").code == "resource.conflict"
    assert DuplicateError("duplicate").code == "resource.duplicate"
    assert InvalidStateError("invalid state").code == "state.invalid"
    assert RepositoryError("repository").code == "repository.error"
    assert IntegrationError("integration").code == "integration.error"

    assert isinstance(DuplicateError("duplicate"), ConflictError)
    assert isinstance(InvalidStateError("invalid"), ConflictError)
    assert isinstance(RepositoryError("repository"), PyCRMKitError)
