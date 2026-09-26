"""Selective OpenAPI contract qualification for PyCRMKit 0.7.0b2."""

from fastapi import FastAPI

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import create_crm_router, install_error_handlers


def _schema() -> dict[str, object]:
    crm = CRM.memory()
    app = FastAPI(title="PyCRMKit test API")
    install_error_handlers(app)
    app.include_router(create_crm_router(lambda: crm), prefix="/crm")
    return app.openapi()


def test_openapi_documents_typed_success_and_error_responses() -> None:
    schema = _schema()
    paths = schema["paths"]

    contact_get = paths["/crm/contacts/{contact_id}"]["get"]
    responses = contact_get["responses"]

    assert {"200", "404", "422", "500"}.issubset(responses)
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ContactResponse"
    )
    assert responses["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )
    assert "resource_not_found" in responses["404"]["content"]["application/json"][
        "examples"
    ]


def test_openapi_documents_request_validation_and_domain_conflict_examples() -> None:
    schema = _schema()
    paths = schema["paths"]

    create_task = paths["/crm/tasks"]["post"]["responses"]
    assert {"201", "409", "422", "500"}.issubset(create_task)

    validation_examples = create_task["422"]["content"]["application/json"]["examples"]
    assert {"domain_validation", "request_validation"} == set(validation_examples)

    complete_task = paths["/crm/tasks/{task_id}/complete"]["post"]["responses"]
    assert "409" in complete_task
    assert "domain_conflict" in complete_task["409"]["content"]["application/json"][
        "examples"
    ]


def test_openapi_keeps_sales_command_surface_typed() -> None:
    schema = _schema()
    paths = schema["paths"]

    convert = paths["/crm/leads/{lead_id}/convert"]["post"]
    assert convert["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/LeadConversionRequest"
    )
    assert convert["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("/OpportunityResponse")
    assert {"404", "409", "422", "500"}.issubset(convert["responses"])
