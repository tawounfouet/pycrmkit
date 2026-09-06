"""Transactional event and audit semantics for MemoryUnitOfWork."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit.audit import AuditEntry, AuditEntryId
from pycrmkit.contacts import Contact, ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.events import DomainEvent, InProcessEventBus
from pycrmkit.exceptions import NotFoundError
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork

NOW = datetime(2026, 9, 6, 19, 0, tzinfo=UTC)


def _contact() -> Contact:
    return Contact(
        id=ContactId(UUID(int=910)),
        created_at=NOW,
        updated_at=NOW,
        first_name="Eventful",
    )


def _event() -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=920)),
        type=EventType("contact.created"),
        schema_version=1,
        aggregate_type="contact",
        aggregate_id=str(_contact().id),
        occurred_at=NOW,
        actor_id="user-1",
        correlation_id="corr-1",
    )


def _audit() -> AuditEntry:
    return AuditEntry(
        id=AuditEntryId(UUID(int=930)),
        actor_id="user-1",
        action="contact.created",
        entity_type="contact",
        entity_id=str(_contact().id),
        occurred_at=NOW,
        correlation_id="corr-1",
    )


def test_audit_entry_commits_atomically_with_domain_state() -> None:
    store = MemoryStore()
    contact = _contact()
    audit = _audit()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.audit.append(audit)
        uow.commit()

    with MemoryUnitOfWork(store) as uow:
        assert uow.contacts.get(contact.id) == contact
        assert uow.audit.get(audit.id) == audit


def test_uncommitted_exit_rolls_back_audit_with_domain_state() -> None:
    store = MemoryStore()
    contact = _contact()
    audit = _audit()

    with MemoryUnitOfWork(store) as uow:
        uow.contacts.save(contact)
        uow.audit.append(audit)

    with MemoryUnitOfWork(store) as uow:
        with pytest.raises(NotFoundError):
            uow.contacts.get(contact.id)
        with pytest.raises(NotFoundError):
            uow.audit.get(audit.id)


def test_domain_events_dispatch_only_after_explicit_commit() -> None:
    store = MemoryStore()
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("contact.created", published.append)
    event = _event()

    with MemoryUnitOfWork(store, event_publisher=bus) as uow:
        uow.add_event(event)
        assert uow.pending_events == (event,)
        assert published == []
        uow.commit()
        assert published == [event]
        assert uow.pending_events == ()


def test_rollback_and_uncommitted_exit_discard_pending_events() -> None:
    store = MemoryStore()
    bus = InProcessEventBus()
    published: list[DomainEvent] = []
    bus.subscribe("contact.created", published.append)

    with MemoryUnitOfWork(store, event_publisher=bus) as uow:
        uow.add_event(_event())
        uow.rollback()

    with MemoryUnitOfWork(store, event_publisher=bus) as uow:
        uow.add_event(_event())

    assert published == []


def test_handler_failure_does_not_undo_already_committed_state() -> None:
    store = MemoryStore()
    bus = InProcessEventBus()
    contact = _contact()

    def fail(event: DomainEvent) -> None:
        del event
        raise RuntimeError("subscriber failed")

    bus.subscribe("contact.created", fail)

    with pytest.raises(RuntimeError, match="subscriber failed"):
        with MemoryUnitOfWork(store, event_publisher=bus) as uow:
            uow.contacts.save(contact)
            uow.add_event(_event())
            uow.commit()

    with MemoryUnitOfWork(store) as uow:
        assert uow.contacts.get(contact.id) == contact
