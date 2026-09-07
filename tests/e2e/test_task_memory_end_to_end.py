"""End-to-end qualification of Tasks through the public CRM facade."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.tasks import TaskQuery, TaskStatus

NOW = datetime(2026, 9, 7, 13, 0, tzinfo=UTC)


def test_contact_task_lifecycle_events_audit_and_queries() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock)
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    contact_ref = EntityReference("contact", contact.id)

    scoped = crm.with_context(actor_id="user-task", correlation_id="corr-e2e-task")
    events: list[DomainEvent] = []
    for event_type in ("task.created", "task.started", "task.completed"):
        scoped.events.subscribe(event_type, events.append)

    task = scoped.tasks.create(
        title="Prepare customer follow-up",
        priority="urgent",
        due_at=NOW + timedelta(hours=2),
        assignee_id="seller-7",
        references=(contact_ref,),
    )
    clock.advance(timedelta(minutes=5))
    task = scoped.tasks.start(task.id)
    clock.advance(timedelta(minutes=10))
    task = scoped.tasks.complete(task.id)

    by_contact = scoped.tasks.list(TaskQuery(reference=contact_ref))
    completed = scoped.tasks.list(TaskQuery(status="completed"))

    assert task.status is TaskStatus.COMPLETED
    assert by_contact.items == (task,)
    assert completed.items == (task,)
    assert [str(event.type) for event in events] == [
        "task.created",
        "task.started",
        "task.completed",
    ]
    assert all(event.correlation_id == "corr-e2e-task" for event in events)

    audit = scoped.audit.by_correlation("corr-e2e-task")
    assert {entry.action for entry in audit.items} == {
        "task.created",
        "task.started",
        "task.completed",
    }
    assert all(entry.entity_type == "task" for entry in audit.items)
