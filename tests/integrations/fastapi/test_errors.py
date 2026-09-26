"""FastAPI error-schema, mapping and handler qualification."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pycrmkit import CRM
from pycrmkit.exceptions import (
    ConflictError,
    IntegrationError,
    InvalidStateError,
    NotFoundError,
    PyCRMKitError,
    RepositoryError,
    ValidationError,
)
from pycrmkit.integrations.fastapi import (
    ErrorResponse,
    create_crm_router,
    install_error_handlers,
    status_code_for_error,
)


def _client() -> TestClient:
    crm = CRM.memory()
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")
    return TestClient(app)


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


def test_domain_error_status_mapping_is_stable() -> None:
    assert status_code_for_error(ValidationError("invalid")) == 422
    assert status_code_for_error(NotFoundError("missing")) == 404
    assert status_code_for_error(ConflictError("conflict")) == 409
    assert status_code_for_error(InvalidStateError("invalid state")) == 409
    assert status_code_for_error(RepositoryError("repository")) == 500
    assert status_code_for_error(IntegrationError("integration")) == 502
    assert status_code_for_error(PyCRMKitError("generic")) == 500


def test_request_validation_uses_stable_error_shape_without_input_echo() -> None:
    response = _client().post("/crm/leads", json={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "request.validation_error"
    assert payload["message"] == "request validation failed"
    assert payload["context"]["errors"]
    assert set(payload) == {"code", "message", "context"}
    assert "input" not in str(payload["context"])


def test_domain_validation_not_found_and_conflict_are_mapped_through_real_routes() -> None:
    client = _client()

    invalid = client.post("/crm/tasks", json={"title": "   "})
    assert invalid.status_code == 422
    assert set(invalid.json()) == {"code", "message", "context"}
    assert invalid.json()["code"] != "request.validation_error"

    missing_id = "00000000-0000-4000-8000-000000000001"
    missing = client.get(f"/crm/contacts/{missing_id}")
    assert missing.status_code == 404
    assert missing.json()["code"] == "contact.not_found"

    created = client.post("/crm/tasks", json={"title": "Prepare proposal"})
    task_id = created.json()["id"]
    assert client.post(f"/crm/tasks/{task_id}/complete").status_code == 200

    conflict = client.post(f"/crm/tasks/{task_id}/complete")
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "task.transition.invalid"
