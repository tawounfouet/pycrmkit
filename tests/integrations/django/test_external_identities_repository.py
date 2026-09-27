"""Run external identity contracts against the Django ORM adapter."""

from datetime import UTC, datetime
from uuid import UUID

from pycrmkit.contacts import ContactId
from pycrmkit.external_identities import ExternalIdentity, ExternalIdentityId
from pycrmkit.integrations.django.repositories import DjangoExternalIdentityRepository
from tests.contracts.external_identities_repository import (
    assert_external_identity_repository_contract,
)


def test_django_external_identity_repository_passes_contract() -> None:
    assert_external_identity_repository_contract(DjangoExternalIdentityRepository())


def test_django_external_identity_restores_typed_contact_owner() -> None:
    repository = DjangoExternalIdentityRepository()
    contact_id = ContactId(UUID("00000000-0000-4000-8000-00000000d401"))
    identity = ExternalIdentity(
        id=ExternalIdentityId(UUID("00000000-0000-4000-8000-00000000d402")),
        created_at=datetime(2026, 9, 27, 17, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 27, 17, 0, tzinfo=UTC),
        system="legacy_crm",
        external_id="django-typed-owner",
        entity_type="contact",
        entity_id=contact_id,
    )

    repository.save(identity)
    reloaded = repository.find("legacy_crm", "django-typed-owner")

    assert reloaded is not None
    assert reloaded.entity_id == contact_id
    assert isinstance(reloaded.entity_id, ContactId)
    assert reloaded.entity == identity.entity
