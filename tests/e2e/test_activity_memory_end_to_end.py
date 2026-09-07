"""End-to-end qualification of Activities through the public CRM facade."""

from __future__ import annotations

from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant, ActivityQuery, ActivityType
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent

NOW = datetime(2026, 9, 7, 11, 0, tzinfo=UTC)


def test_contact_organization_activity_events_and_audit() -> None:
    crm = CRM.memory(clock=FixedClock(NOW))
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")

    scoped = crm.with_context(actor_id="user-activity", correlation_id="corr-e2e-activity")
    events: list[DomainEvent] = []
    scoped.events.subscribe("activity.created", events.append)

    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)
    activity = scoped.activities.log(
        type="meeting",
        subject="Discovery meeting",
        participants=(
            ActivityParticipant(contact_ref, role="customer", is_primary=True),
        ),
        references=(organization_ref,),
        source="manual",
    )

    by_contact = scoped.activities.list(ActivityQuery(participant=contact_ref))
    by_org = scoped.activities.list(ActivityQuery(reference=organization_ref))

    assert by_contact.items == (activity,)
    assert by_org.items == (activity,)
    assert activity.type is ActivityType.MEETING
    assert [str(event.type) for event in events] == ["activity.created"]
    assert events[0].correlation_id == "corr-e2e-activity"

    audit = scoped.audit.by_correlation("corr-e2e-activity")
    assert audit.total == 1
    assert audit.items[0].entity_type == "activity"
    assert audit.items[0].entity_id == str(activity.id)
