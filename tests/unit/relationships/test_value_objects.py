from __future__ import annotations

from uuid import UUID

import pytest

from pycrmkit.contacts import ContactId
from pycrmkit.exceptions import ValidationError
from pycrmkit.organizations import OrganizationId
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipEntityKind,
    RelationshipType,
)


def test_relationship_type_is_normalized() -> None:
    assert RelationshipType(" Account  Manager ").code == "account-manager"
    assert RelationshipType("PARENT_COMPANY").code == "parent-company"


def test_relationship_endpoints_preserve_typed_ids() -> None:
    contact_id = ContactId(UUID("00000000-0000-4000-8000-000000000211"))
    organization_id = OrganizationId(UUID("00000000-0000-4000-8000-000000000212"))

    contact = RelationshipEndpoint.contact(contact_id)
    organization = RelationshipEndpoint.organization(organization_id)

    assert contact.kind is RelationshipEntityKind.CONTACT
    assert contact.id == contact_id
    assert organization.kind is RelationshipEntityKind.ORGANIZATION
    assert organization.id == organization_id


def test_relationship_endpoint_rejects_mismatched_id_type() -> None:
    organization_id = OrganizationId(UUID("00000000-0000-4000-8000-000000000212"))
    with pytest.raises(ValidationError, match="ContactId"):
        RelationshipEndpoint(RelationshipEntityKind.CONTACT, organization_id)
