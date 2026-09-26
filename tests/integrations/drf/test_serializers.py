"""Serializer contract tests for the optional DRF bridge."""

from __future__ import annotations

from uuid import UUID

from pycrmkit.contacts import ContactStatus
from pycrmkit.integrations.django.drf.serializers import (
    ContactCreateSerializer,
    ContactUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationUpdateSerializer,
    RelationshipCreateSerializer,
    RelationshipUpdateSerializer,
)
from pycrmkit.organizations import OrganizationStatus
from pycrmkit.relationships import RelationshipEntityKind


def test_contact_create_serializer_maps_nested_values_to_domain() -> None:
    serializer = ContactCreateSerializer(
        data={
            "first_name": " Ada ",
            "status": "active",
            "owner_id": "00000000-0000-4000-8000-000000000001",
            "emails": [
                {
                    "value": "ADA@Example.COM",
                    "is_primary": True,
                    "verification": "verified",
                }
            ],
            "phones": [{"value": "+33 6 12 34 56 78"}],
            "addresses": [
                {
                    "line1": "1 Main Street",
                    "city": "Paris",
                    "country_code": "fr",
                }
            ],
            "metadata": {"source": "serializer-test"},
        }
    )

    assert serializer.is_valid(), serializer.errors
    payload = serializer.to_domain_kwargs()

    assert payload["status"] is ContactStatus.ACTIVE
    assert payload["owner_id"] is not None
    assert payload["emails"][0].normalized == "ada@example.com"
    assert payload["phones"][0].normalized == "+33612345678"
    assert payload["addresses"][0].country_code == "FR"
    assert payload["metadata"] == {"source": "serializer-test"}


def test_contact_update_preserves_omitted_vs_explicit_null() -> None:
    serializer = ContactUpdateSerializer(data={"first_name": None}, partial=True)

    assert serializer.is_valid(), serializer.errors
    update = serializer.to_domain()

    assert update.first_name is None
    assert repr(update.last_name) == "UNSET"
    assert repr(update.owner_id) == "UNSET"


def test_contact_update_rejects_null_non_nullable_status() -> None:
    serializer = ContactUpdateSerializer(data={"status": None}, partial=True)

    assert not serializer.is_valid()
    assert "status" in serializer.errors


def test_organization_serializers_preserve_domain_types_and_partial_clear() -> None:
    create = OrganizationCreateSerializer(
        data={
            "legal_name": " Example SAS ",
            "status": "active",
            "domains": [{"value": "Example.COM", "is_primary": True}],
            "addresses": [
                {
                    "line1": "2 Avenue",
                    "city": "Paris",
                    "country_code": "fr",
                }
            ],
        }
    )
    assert create.is_valid(), create.errors
    payload = create.to_domain_kwargs()

    assert payload["status"] is OrganizationStatus.ACTIVE
    assert payload["domains"][0].normalized == "example.com"
    assert payload["addresses"][0].country_code == "FR"

    update_serializer = OrganizationUpdateSerializer(
        data={"trading_name": None},
        partial=True,
    )
    assert update_serializer.is_valid(), update_serializer.errors
    update = update_serializer.to_domain()
    assert update.trading_name is None
    assert repr(update.legal_name) == "UNSET"


def test_relationship_serializers_map_typed_endpoints_and_partial_fields() -> None:
    contact_id = UUID("00000000-0000-4000-8000-000000000010")
    organization_id = UUID("00000000-0000-4000-8000-000000000011")
    create = RelationshipCreateSerializer(
        data={
            "source": {"kind": "contact", "id": str(contact_id)},
            "target": {"kind": "organization", "id": str(organization_id)},
            "relationship_type": " employee_of ",
            "role": "CTO",
        }
    )

    assert create.is_valid(), create.errors
    payload = create.to_domain_kwargs()

    assert payload["source"].kind is RelationshipEntityKind.CONTACT
    assert payload["source"].id.value == contact_id
    assert payload["target"].kind is RelationshipEntityKind.ORGANIZATION
    assert payload["target"].id.value == organization_id
    assert str(payload["relationship_type"]) == "employee-of"

    update_serializer = RelationshipUpdateSerializer(
        data={"title": None},
        partial=True,
    )
    assert update_serializer.is_valid(), update_serializer.errors
    update = update_serializer.to_domain()
    assert update.title is None
    assert repr(update.role) == "UNSET"
