"""Facade-backed DRF router integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent


def _crm() -> CRM:
    return CRM.memory(clock=FixedClock(datetime(2026, 9, 26, 21, 0, tzinfo=UTC)))


def test_contact_crud_archive_pagination_and_request_context() -> None:
    crm = _crm()
    events: list[DomainEvent] = []
    crm.events.subscribe("contact.created", events.append)
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        created = client.post(
            "/crm/contacts/",
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "emails": [
                    {
                        "value": "ada@example.com",
                        "is_primary": True,
                    }
                ],
            },
            format="json",
            HTTP_X_ACTOR_ID="user-42",
            HTTP_X_CORRELATION_ID="corr-drf-1",
        )

        assert created.status_code == status.HTTP_201_CREATED
        contact_id = created.data["id"]
        assert created.data["display_name"] == "Ada Lovelace"
        assert events[0].actor_id == "user-42"
        assert events[0].correlation_id == "corr-drf-1"

        listed = client.get("/crm/contacts/?limit=1&offset=0")
        assert listed.status_code == status.HTTP_200_OK
        assert listed.data["total"] == 1
        assert listed.data["limit"] == 1
        assert listed.data["offset"] == 0
        assert listed.data["has_next"] is False
        assert listed.data["items"][0]["id"] == contact_id

        fetched = client.get(f"/crm/contacts/{contact_id}/")
        assert fetched.status_code == status.HTTP_200_OK
        assert fetched.data["emails"][0]["value"] == "ada@example.com"

        updated = client.patch(
            f"/crm/contacts/{contact_id}/",
            {"first_name": "Augusta"},
            format="json",
        )
        assert updated.status_code == status.HTTP_200_OK
        assert updated.data["first_name"] == "Augusta"

        archived = client.post(f"/crm/contacts/{contact_id}/archive/")
        assert archived.status_code == status.HTTP_200_OK
        assert archived.data["status"] == "archived"

        put = client.put(
            f"/crm/contacts/{contact_id}/",
            {"first_name": "Should not be accepted"},
            format="json",
        )
        assert put.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_organization_and_relationship_flow_uses_public_facade() -> None:
    crm = _crm()
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        contact = client.post(
            "/crm/contacts/",
            {"display_name": "DRF Contact"},
            format="json",
        )
        organization = client.post(
            "/crm/organizations/",
            {
                "legal_name": "Example SAS",
                "domains": [{"value": "example.com", "is_primary": True}],
            },
            format="json",
        )

        assert contact.status_code == 201
        assert organization.status_code == 201

        relationship = client.post(
            "/crm/relationships/",
            {
                "source": {"kind": "contact", "id": contact.data["id"]},
                "target": {
                    "kind": "organization",
                    "id": organization.data["id"],
                },
                "relationship_type": "employee_of",
                "role": "CTO",
            },
            format="json",
        )
        assert relationship.status_code == 201
        relationship_id = relationship.data["id"]
        assert relationship.data["relationship_type"] == "employee-of"

        updated = client.patch(
            f"/crm/relationships/{relationship_id}/",
            {"title": "Chief Technology Officer"},
            format="json",
        )
        assert updated.status_code == 200
        assert updated.data["title"] == "Chief Technology Officer"

        ended = client.post(f"/crm/relationships/{relationship_id}/end/")
        assert ended.status_code == 200
        assert ended.data["is_ended"] is True


def test_domain_errors_use_stable_error_response_shape() -> None:
    crm = _crm()
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        invalid_domain = client.post(
            "/crm/contacts/",
            {
                "display_name": "Invalid email",
                "emails": [{"value": "not-an-email"}],
            },
            format="json",
        )
        assert invalid_domain.status_code == 422
        assert invalid_domain.data["code"] == "contact.email.invalid"
        assert invalid_domain.data["message"]
        assert "context" in invalid_domain.data

        missing = client.get(
            "/crm/contacts/00000000-0000-4000-8000-000000009999/"
        )
        assert missing.status_code == 404
        assert missing.data["code"] == "contact.not_found"


def test_request_validation_is_normalized_and_does_not_echo_input() -> None:
    crm = _crm()
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        invalid = client.post(
            "/crm/contacts/",
            {
                "display_name": "Do not echo me",
                "status": "definitely-not-a-status",
            },
            format="json",
        )

        assert invalid.status_code == 400
        assert invalid.data["code"] == "request.validation_error"
        assert invalid.data["message"] == "request validation failed"
        assert invalid.data["context"]["errors"][0]["location"] == ["status", "0"]
        assert "Do not echo me" not in str(invalid.data)


def test_invalid_path_uuid_and_invalid_pagination_are_request_errors() -> None:
    crm = _crm()
    client = APIClient()

    with override_settings(PYCRMKIT_CRM_FACTORY=lambda: crm):
        invalid_id = client.get("/crm/contacts/not-a-uuid/")
        assert invalid_id.status_code == 400
        assert invalid_id.data["code"] == "request.validation_error"

        invalid_page = client.get("/crm/contacts/?limit=0")
        assert invalid_page.status_code == 400
        assert invalid_page.data["code"] == "request.validation_error"
