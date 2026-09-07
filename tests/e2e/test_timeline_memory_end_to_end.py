from datetime import UTC, datetime, timedelta

from pycrmkit import CRM, CRMConfig
from pycrmkit.activities import ActivityParticipant, ActivityType
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.timeline import TimelineEntryKind


def test_contact_and_organization_timeline_projects_activity_and_task_lifecycle() -> None:
    clock = FixedClock(datetime(2026, 9, 7, 9, tzinfo=UTC))
    crm = CRM.memory(clock=clock)
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")
    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    clock.advance(timedelta(hours=1))
    meeting = crm.activities.log(
        type=ActivityType.MEETING,
        occurred_at=clock.now(),
        subject="Renewal review",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
    )

    clock.advance(timedelta(hours=1))
    task = crm.tasks.create(
        title="Send renewal proposal",
        references=(contact_ref, organization_ref),
    )
    clock.advance(timedelta(hours=1))
    crm.tasks.complete(task.id)

    contact_timeline = crm.timeline.for_contact(contact.id)
    organization_timeline = crm.timeline.for_organization(organization.id)

    assert contact_timeline.total == 3
    assert organization_timeline.total == 3
    assert [str(item.event_type) for item in contact_timeline.items] == [
        "task.completed",
        "task.created",
        "activity.created",
    ]
    assert contact_timeline.items[-1].entity.id == meeting.id
    assert organization_timeline.items == contact_timeline.items

    activities = crm.timeline.for_contact(contact.id, kind=TimelineEntryKind.ACTIVITY)
    assert activities.total == 1
    assert activities.items[0].title == "Renewal review"


def test_timeline_projection_remains_available_when_public_events_and_audit_are_disabled() -> None:
    clock = FixedClock(datetime(2026, 9, 7, 9, tzinfo=UTC))
    crm = CRM.memory(
        clock=clock,
        config=CRMConfig(events_enabled=False, audit_enabled=False),
    )
    contact = crm.contacts.create(display_name="Grace Hopper")
    reference = EntityReference("contact", contact.id)
    crm.tasks.create(title="Call customer", references=(reference,))

    page = crm.timeline.for_contact(contact.id)
    assert page.total == 1
    assert str(page.items[0].event_type) == "task.created"
