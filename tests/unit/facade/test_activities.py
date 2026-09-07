"""Activities facade transaction/event/audit behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.activities import ActivityUpdate
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent

NOW = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def test_activity_facade_logs_and_emits_post_commit_event_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW)).with_context(
        actor_id="sales-user",
        correlation_id="corr-activity",
    )
    events: list[DomainEvent] = []
    crm.events.subscribe("activity.created", events.append)

    activity = crm.activities.log(
        type="call",
        subject="Commercial follow-up",
        direction="outbound",
        duration_seconds=480,
    )

    assert crm.activities.get(activity.id) == activity
    assert len(events) == 1
    assert events[0].aggregate_id == str(activity.id)
    assert events[0].payload["activity_type"] == "call"
    assert events[0].actor_id == "sales-user"
    assert events[0].correlation_id == "corr-activity"

    audit = crm.audit.by_correlation("corr-activity")
    assert audit.total == 1
    assert audit.items[0].action == "activity.created"
    assert "Commercial follow-up" not in repr(audit.items[0].changes)


def test_activity_facade_update_emits_activity_updated() -> None:
    clock = FixedClock(NOW)
    crm = CRM.memory(clock=clock).with_context(correlation_id="corr-update")
    events: list[DomainEvent] = []
    crm.events.subscribe("activity.updated", events.append)
    activity = crm.activities.log(type="note", description="Draft")

    clock.advance(timedelta(minutes=10))
    updated = crm.activities.update(
        activity.id,
        ActivityUpdate(description="Final"),
    )

    assert updated.description == "Final"
    assert [str(event.type) for event in events] == ["activity.updated"]
    actions = {entry.action for entry in crm.audit.by_correlation("corr-update").items}
    assert actions == {"activity.created", "activity.updated"}
