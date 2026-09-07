from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant, ActivityQuery, ActivityService, ActivityType
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent
from pycrmkit.storage.memory import MemoryStore, MemoryUnitOfWork
from pycrmkit.timeline import TimelineEntryKind, TimelineProjector


def test_rc_multi_entity_historical_activity_and_task_lifecycle_are_coherent() -> None:
    clock = FixedClock(datetime(2026, 9, 7, 10, tzinfo=UTC))
    crm = CRM.memory(clock=clock).with_context(
        actor_id="rc-user",
        correlation_id="rc-correlation",
    )
    contact = crm.contacts.create(first_name="Ada", last_name="Lovelace")
    organization = crm.organizations.create(legal_name="Analytical Engines Ltd")
    contact_ref = EntityReference("contact", contact.id)
    organization_ref = EntityReference("organization", organization.id)

    historical_at = datetime(2024, 1, 15, 9, tzinfo=UTC)
    historical = crm.activities.log(
        type=ActivityType.MEETING,
        occurred_at=historical_at,
        subject="Imported discovery meeting",
        participants=(ActivityParticipant(contact_ref, is_primary=True),),
        references=(organization_ref,),
        source="legacy-crm",
    )

    clock.advance(timedelta(hours=1))
    task = crm.tasks.create(
        title="Prepare renewal",
        priority="high",
        references=(contact_ref, organization_ref),
    )
    clock.advance(timedelta(hours=1))
    crm.tasks.start(task.id)
    clock.advance(timedelta(hours=1))
    crm.tasks.complete(task.id)
    clock.advance(timedelta(hours=1))
    crm.tasks.reopen(task.id)
    clock.advance(timedelta(hours=1))
    crm.tasks.cancel(task.id)

    contact_history = crm.timeline.for_contact(contact.id)
    organization_history = crm.timeline.for_organization(organization.id)

    assert contact_history.total == 6
    assert organization_history.items == contact_history.items
    assert [str(entry.event_type) for entry in contact_history.items] == [
        "task.cancelled",
        "task.reopened",
        "task.completed",
        "task.started",
        "task.created",
        "activity.created",
    ]
    imported = contact_history.items[-1]
    assert imported.entity.id == historical.id
    assert imported.occurred_at == historical_at
    assert imported.actor_id == "rc-user"
    assert imported.correlation_id == "rc-correlation"


def test_rc_timeline_pagination_filters_and_half_open_window_are_stable() -> None:
    clock = FixedClock(datetime(2026, 9, 7, 8, tzinfo=UTC))
    crm = CRM.memory(clock=clock)
    contact = crm.contacts.create(display_name="Grace Hopper")
    reference = EntityReference("contact", contact.id)

    task = crm.tasks.create(title="Call customer", references=(reference,))
    created_at = clock.now()
    clock.advance(timedelta(hours=1))
    crm.tasks.start(task.id)
    started_at = clock.now()
    clock.advance(timedelta(hours=1))
    crm.tasks.complete(task.id)
    completed_at = clock.now()

    first = crm.timeline.for_contact(
        contact.id,
        OffsetPageRequest(limit=1, offset=0),
        kind=TimelineEntryKind.TASK,
    )
    second = crm.timeline.for_contact(
        contact.id,
        OffsetPageRequest(limit=1, offset=1),
        kind=TimelineEntryKind.TASK,
    )
    assert first.total == 3
    assert first.has_next is True
    assert second.has_previous is True
    assert str(first.items[0].event_type) == "task.completed"
    assert str(second.items[0].event_type) == "task.started"

    exact_middle = crm.timeline.for_contact(
        contact.id,
        event_type="task.started",
        occurred_from=started_at,
        occurred_until=completed_at,
    )
    assert [str(entry.event_type) for entry in exact_middle.items] == ["task.started"]

    creation_only = crm.timeline.for_contact(
        contact.id,
        occurred_from=created_at,
        occurred_until=started_at,
    )
    assert [str(entry.event_type) for entry in creation_only.items] == ["task.created"]


def test_rc_projection_rolls_back_with_the_source_transaction() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 7, 12, tzinfo=UTC))
    ids = UUID4Factory()
    reference = EntityReference("contact", ids.new(ContactId))

    with MemoryUnitOfWork(store) as uow:
        activity = ActivityService(
            uow.activities,
            id_factory=ids,
            clock=clock,
        ).log(
            type="note",
            subject="Will roll back",
            references=(reference,),
        )
        event = DomainEvent.create(
            id_factory=ids,
            clock=clock,
            type="activity.created",
            aggregate_type="activity",
            aggregate_id=activity.id,
        )
        entry = TimelineProjector(
            uow.timeline,
            activities=uow.activities,
            tasks=uow.tasks,
        ).project(event)
        assert entry is not None
        assert uow.timeline.list_for_reference(
            reference,
            OffsetPageRequest(),
        ).total == 1
        uow.rollback()

    with MemoryUnitOfWork(store) as uow:
        assert uow.activities.list(ActivityQuery(), OffsetPageRequest()).total == 0
        assert uow.timeline.list_for_reference(reference, OffsetPageRequest()).total == 0


def test_rc_projection_replay_is_idempotent() -> None:
    store = MemoryStore()
    clock = FixedClock(datetime(2026, 9, 7, 13, tzinfo=UTC))
    ids = UUID4Factory()
    reference = EntityReference("contact", ids.new(ContactId))

    with MemoryUnitOfWork(store) as uow:
        activity = ActivityService(
            uow.activities,
            id_factory=ids,
            clock=clock,
        ).log(type="note", subject="Replay safe", references=(reference,))
        event = DomainEvent.create(
            id_factory=ids,
            clock=clock,
            type="activity.created",
            aggregate_type="activity",
            aggregate_id=activity.id,
        )
        projector = TimelineProjector(
            uow.timeline,
            activities=uow.activities,
            tasks=uow.tasks,
        )
        first = projector.project(event)
        second = projector.project(event)
        assert first == second
        assert uow.timeline.list_for_reference(reference, OffsetPageRequest()).total == 1
