"""Correlation, causation and actor propagation tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from pycrmkit import CRM, CRMContext
from pycrmkit.core.events import EventId
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.exceptions import ValidationError

NOW = datetime(2026, 9, 26, 7, 0, tzinfo=UTC)


def _event(
    *,
    event_id: int = 1,
    actor_id: str | None = "user-42",
    correlation_id: str | None = "corr-root",
) -> DomainEvent:
    return DomainEvent(
        id=EventId(UUID(int=event_id)),
        type="contact.created",  # type: ignore[arg-type]
        schema_version=1,
        aggregate_type="contact",
        aggregate_id="contact-1",
        occurred_at=NOW,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )


def test_context_from_event_inherits_actor_correlation_and_direct_causation() -> None:
    parent = _event()

    context = CRMContext.from_event(parent)

    assert context.actor_id == "user-42"
    assert context.correlation_id == "corr-root"
    assert context.causation_id == parent.id


def test_context_from_uncorrelated_event_uses_parent_id_as_trace_root() -> None:
    parent = _event(event_id=2, correlation_id=None)

    context = CRMContext.from_event(parent)

    assert context.correlation_id == str(parent.id)
    assert context.causation_id == parent.id


def test_context_rejects_non_event_causation_identifier() -> None:
    with pytest.raises(ValidationError) as error:
        CRMContext(causation_id="not-an-event-id")  # type: ignore[arg-type]

    assert error.value.code == "crm.causation_id.invalid"


def test_with_event_propagates_trace_through_nested_facade_mutations() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    root_events: list[DomainEvent] = []
    child_events: list[DomainEvent] = []
    crm.events.subscribe("contact.created", root_events.append)
    crm.events.subscribe("task.created", child_events.append)

    crm.with_context(
        actor_id="agent-7",
        correlation_id="request-900",
    ).contacts.create(display_name="Trace Root")
    root = root_events[0]

    task = crm.with_event(root).tasks.create(title="Follow up")

    assert child_events[0].actor_id == "agent-7"
    assert child_events[0].correlation_id == "request-900"
    assert child_events[0].causation_id == root.id

    completed: list[DomainEvent] = []
    crm.events.subscribe("task.completed", completed.append)
    crm.with_event(child_events[0]).tasks.complete(task.id)

    assert completed[0].actor_id == "agent-7"
    assert completed[0].correlation_id == "request-900"
    assert completed[0].causation_id == child_events[0].id


def test_with_event_shares_backend_with_originating_crm() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    parent = _event()

    child = crm.with_event(parent)
    contact = child.contacts.create(display_name="Shared Backend")

    assert crm.contacts.get(contact.id) == contact
