"""Reusable ExternalIdentityRepository conformance assertions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import ConflictError, DuplicateError
from pycrmkit.external_identities import (
    ExternalIdentity,
    ExternalIdentityId,
    ExternalIdentityRepository,
)

NOW = datetime(2026, 9, 26, 22, 0, tzinfo=UTC)


def make_identity(
    number: int,
    *,
    system: str,
    external_id: str,
    entity: EntityReference,
) -> ExternalIdentity:
    return ExternalIdentity(
        id=ExternalIdentityId(UUID(int=number)),
        created_at=NOW,
        updated_at=NOW,
        system=system,
        external_id=external_id,
        entity_type=entity.kind,
        entity_id=entity.id,
        metadata={"fixture": number},
    )


def assert_external_identity_repository_contract(
    repository: ExternalIdentityRepository,
) -> None:
    contact = EntityReference("contact", EntityId(UUID(int=101)))
    organization = EntityReference("organization", EntityId(UUID(int=202)))

    hubspot = make_identity(
        1,
        system="hubspot",
        external_id="123456",
        entity=contact,
    )
    salesforce = make_identity(
        2,
        system="salesforce",
        external_id="003-A",
        entity=contact,
    )

    repository.save(hubspot)
    repository.save(salesforce)

    assert repository.find("hubspot", "123456") == hubspot
    assert repository.find("missing", "1") is None

    page = repository.list_for_entity(
        contact,
        OffsetPageRequest(limit=1, offset=0),
    )
    assert page.total == 2
    assert page.items == (hubspot,)

    second = repository.list_for_entity(
        contact,
        OffsetPageRequest(limit=10, offset=1),
    )
    assert second.items == (salesforce,)

    with pytest.raises(ConflictError, match="another entity"):
        repository.save(
            make_identity(
                3,
                system="hubspot",
                external_id="123456",
                entity=organization,
            )
        )

    with pytest.raises(DuplicateError):
        repository.save(
            make_identity(
                4,
                system="hubspot",
                external_id="123456",
                entity=contact,
            )
        )

    assert repository.remove("hubspot", "123456") is True
    assert repository.remove("hubspot", "123456") is False
    assert repository.find("hubspot", "123456") is None
