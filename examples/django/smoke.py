"""Two-process E2E smoke for the Django + PostgreSQL reference application."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

EXPECTED_VERSION = "0.8.0"


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pycrmkit_example.settings")
    import django

    django.setup()


def _expect(response, status_code: int) -> None:
    if response.status_code != status_code:
        raise AssertionError(
            f"expected HTTP {status_code}, got {response.status_code}: {response.data!r}"
        )


def seed(state_path: Path) -> None:
    """Create a connected CRM graph through HTTP and persist only its IDs."""

    _setup_django()

    from rest_framework.test import APIClient

    from pycrmkit import __version__

    client = APIClient()

    health = client.get("/health/")
    _expect(health, 200)
    assert health.json() == {"status": "ok", "database": "postgresql"}

    contact = client.post(
        "/crm/contacts/",
        {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "emails": [
                {
                    "value": "ada.django@example.com",
                    "is_primary": True,
                    "verification": "verified",
                }
            ],
            "addresses": [
                {
                    "line1": "1 Analytical Engine Way",
                    "city": "London",
                    "country_code": "GB",
                    "is_primary": True,
                }
            ],
            "metadata": {"reference_app": "django-postgresql"},
        },
        format="json",
        HTTP_X_ACTOR_ID="django-e2e",
        HTTP_X_CORRELATION_ID="django-e2e-seed",
    )
    _expect(contact, 201)

    organization = client.post(
        "/crm/organizations/",
        {
            "legal_name": "Analytical Engines Ltd",
            "domains": [{"value": "analytical.example", "is_primary": True}],
            "metadata": {"reference_app": "django-postgresql"},
        },
        format="json",
    )
    _expect(organization, 201)

    from pycrmkit_example.crm import get_crm

    external_identity = get_crm().external_identities.attach(
        get_crm().contacts.get(contact.data["id"]),
        system="hubspot",
        external_id="django-contact-ada-001",
        metadata={"reference_app": "django-postgresql"},
    )
    assert external_identity.system == "hubspot"

    relationship = client.post(
        "/crm/relationships/",
        {
            "source": {"kind": "contact", "id": contact.data["id"]},
            "target": {"kind": "organization", "id": organization.data["id"]},
            "relationship_type": "employee_of",
            "role": "Pioneer",
            "valid_from": "2026-09-26T20:00:00Z",
        },
        format="json",
    )
    _expect(relationship, 201)

    state_path.write_text(
        json.dumps(
            {
                "contact_id": str(contact.data["id"]),
                "organization_id": str(organization.data["id"]),
                "relationship_id": str(relationship.data["id"]),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    assert __version__ == EXPECTED_VERSION
    print(f"PyCRMKit {__version__} Django/PostgreSQL seed: OK")


def verify(state_path: Path) -> None:
    """Re-open persisted data in a fresh Python/Django process and mutate it."""

    _setup_django()

    from django.apps import apps
    from django.contrib import admin
    from django.db import connection
    from django.db.migrations.recorder import MigrationRecorder
    from rest_framework.test import APIClient

    from pycrmkit import __version__
    from pycrmkit.integrations.django.models import (
        ContactModel,
        OrganizationModel,
        RelationshipModel,
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    client = APIClient()

    from pycrmkit_example.crm import get_crm

    external_identity = get_crm().external_identities.resolve(
        "hubspot",
        "django-contact-ada-001",
    )
    assert str(external_identity.entity_id) == state["contact_id"]

    contact = client.get(f"/crm/contacts/{state['contact_id']}/")
    _expect(contact, 200)
    assert contact.data["display_name"] == "Ada Lovelace"
    assert contact.data["emails"][0]["value"] == "ada.django@example.com"

    organization = client.get(f"/crm/organizations/{state['organization_id']}/")
    _expect(organization, 200)
    assert organization.data["legal_name"] == "Analytical Engines Ltd"

    relationship = client.get(f"/crm/relationships/{state['relationship_id']}/")
    _expect(relationship, 200)
    assert relationship.data["relationship_type"] == "employee-of"

    page = client.get("/crm/contacts/?limit=1&offset=0")
    _expect(page, 200)
    assert page.data["total"] >= 1
    assert page.data["items"][0]["id"] == state["contact_id"]

    updated = client.patch(
        f"/crm/contacts/{state['contact_id']}/",
        {"display_name": "Ada Lovelace — persisted"},
        format="json",
        HTTP_X_CORRELATION_ID="django-e2e-verify",
    )
    _expect(updated, 200)
    assert updated.data["display_name"] == "Ada Lovelace — persisted"

    ended = client.post(f"/crm/relationships/{state['relationship_id']}/end/")
    _expect(ended, 200)
    assert ended.data["is_ended"] is True

    admin_login = client.get("/admin/login/")
    assert admin_login.status_code == 200

    assert apps.get_app_config("pycrmkit_crm").name == "pycrmkit.integrations.django"
    assert admin.site.is_registered(ContactModel)
    assert admin.site.is_registered(OrganizationModel)
    assert admin.site.is_registered(RelationshipModel)
    assert ("pycrmkit_crm", "0001_initial") in MigrationRecorder(
        connection
    ).applied_migrations()

    assert ContactModel.objects.filter(pk=state["contact_id"]).exists()
    assert OrganizationModel.objects.filter(pk=state["organization_id"]).exists()
    assert RelationshipModel.objects.filter(pk=state["relationship_id"]).exists()
    assert __version__ == EXPECTED_VERSION

    print(f"PyCRMKit {__version__} Django/PostgreSQL verify: OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("seed", "verify"))
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "seed":
        seed(args.state)
    else:
        verify(args.state)


if __name__ == "__main__":
    main()
