"""Reusable AuditRepository contract suite."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from pycrmkit.audit import AuditEntry, AuditEntryId, AuditRepository
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.exceptions import DuplicateError, NotFoundError

NOW = datetime(2026, 9, 6, 18, 0, tzinfo=UTC)


def _entry(
    sequence: int,
    *,
    entity_id: str = "entity-1",
    actor_id: str | None = "user-1",
    correlation_id: str | None = "corr-1",
    occurred_at: datetime | None = None,
) -> AuditEntry:
    return AuditEntry(
        id=AuditEntryId(UUID(int=sequence)),
        actor_id=actor_id,
        action="contact.updated",
        entity_type="contact",
        entity_id=entity_id,
        occurred_at=occurred_at or NOW,
        changes={"sequence": sequence},
        correlation_id=correlation_id,
    )


def assert_audit_repository_contract(repository: AuditRepository) -> None:
    """Execute backend-neutral audit repository semantics."""

    first = _entry(1, occurred_at=NOW + timedelta(seconds=2))
    second = _entry(2, occurred_at=NOW)
    third = _entry(3, entity_id="entity-2", actor_id="user-2", correlation_id="corr-2")

    repository.append(first)
    repository.append(second)
    repository.append(third)

    assert repository.get(first.id) == first
    assert repository.find(AuditEntryId(UUID(int=999))) is None
    with pytest.raises(NotFoundError):
        repository.get(AuditEntryId(UUID(int=999)))
    with pytest.raises(DuplicateError):
        repository.append(first)

    entity_page = repository.list_for_entity(
        "CONTACT",
        "entity-1",
        OffsetPageRequest(limit=10, offset=0),
    )
    assert entity_page.items == (second, first)
    assert entity_page.total == 2

    actor_page = repository.list_by_actor("user-1", OffsetPageRequest(limit=10, offset=0))
    assert actor_page.items == (second, first)

    correlation_page = repository.list_by_correlation(
        "corr-2",
        OffsetPageRequest(limit=10, offset=0),
    )
    assert correlation_page.items == (third,)
