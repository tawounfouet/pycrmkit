"""AuditService behavior and event-context bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from pycrmkit.audit import AuditEntryId, AuditService
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.storage.memory import MemoryAuditRepository

IdT = TypeVar("IdT", bound=UUIDId)


class DeterministicFactory:
    def new(self, id_type: type[IdT]) -> IdT:
        return id_type(UUID(int=700))


def test_record_appends_explicit_minimized_changes() -> None:
    repository = MemoryAuditRepository()
    service = AuditService(
        repository,
        id_factory=DeterministicFactory(),
        clock=FixedClock(datetime(2026, 9, 6, 18, 30, tzinfo=UTC)),
    )
    entry = service.record(
        action="contact.email_changed",
        entity_type="contact",
        entity_id="contact-1",
        actor_id="user-1",
        changes={"field": "email"},
        correlation_id="corr-1",
    )
    assert entry.id == AuditEntryId(UUID(int=700))
    assert repository.get(entry.id) == entry


def test_record_event_copies_context_but_not_payload_by_default() -> None:
    repository = MemoryAuditRepository()
    service = AuditService(
        repository,
        id_factory=DeterministicFactory(),
        clock=FixedClock(datetime(2026, 9, 6, 18, 30, tzinfo=UTC)),
    )
    event = DomainEvent(
        id=EventId(UUID(int=800)),
        type=EventType("contact.updated"),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-1",
        occurred_at=datetime(2026, 9, 6, 18, 0, tzinfo=UTC),
        actor_id="user-1",
        correlation_id="corr-1",
        payload={"email": "pii@example.com"},
    )
    entry = service.record_event(event)
    assert entry.action == "contact.updated"
    assert entry.actor_id == "user-1"
    assert entry.correlation_id == "corr-1"
    assert dict(entry.changes) == {}
