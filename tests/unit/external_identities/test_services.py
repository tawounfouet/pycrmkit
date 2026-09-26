"""External identity domain/service behavior."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.exceptions import ConflictError, NotFoundError, ValidationError
from pycrmkit.external_identities import (
    ExternalIdentityService,
    normalize_external_id,
    normalize_external_system,
)
from pycrmkit.storage.memory import MemoryExternalIdentityRepository

NOW = datetime(2026, 9, 26, 22, 15, tzinfo=UTC)


def test_normalization_is_provider_neutral_and_external_id_case_preserving() -> None:
    assert normalize_external_system(" HubSpot CRM ") == "hubspot_crm"
    assert normalize_external_id("  AbC-123  ") == "AbC-123"

    with pytest.raises(ValidationError):
        normalize_external_system("")
    with pytest.raises(ValidationError):
        normalize_external_id("   ")


def test_attach_is_idempotent_for_same_owner_and_conflicts_for_other_owner() -> None:
    repository = MemoryExternalIdentityRepository()
    service = ExternalIdentityService(repository, clock=FixedClock(NOW))
    contact = EntityReference("contact", EntityId(UUID(int=1)))
    other = EntityReference("contact", EntityId(UUID(int=2)))

    first = service.attach(
        contact,
        system="HubSpot",
        external_id="42",
        metadata={"source": "initial"},
    )
    replay = service.attach(
        contact,
        system="hubspot",
        external_id="42",
        metadata={"source": "retry"},
    )

    assert replay == first
    assert replay.metadata == {"source": "initial"}

    with pytest.raises(ConflictError) as error:
        service.attach(other, system="hubspot", external_id="42")
    assert error.value.code == "external_identity.owner.conflict"


def test_resolve_list_and_detach_contract() -> None:
    repository = MemoryExternalIdentityRepository()
    service = ExternalIdentityService(repository, clock=FixedClock(NOW))
    contact = EntityReference("contact", EntityId(UUID(int=10)))

    attached = service.attach(contact, system="salesforce", external_id="003XYZ")
    assert service.resolve("salesforce", "003XYZ") == attached
    assert service.list_for_entity(contact).items == (attached,)
    assert service.detach("salesforce", "003XYZ") is True
    assert service.detach("salesforce", "003XYZ") is False

    with pytest.raises(NotFoundError) as error:
        service.resolve("salesforce", "003XYZ")
    assert error.value.code == "external_identity.not_found"
