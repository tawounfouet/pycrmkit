from datetime import UTC, datetime
from uuid import uuid4

from pycrmkit.activities import Activity, ActivityId, ActivityParticipant, ActivityType
from pycrmkit.contacts import ContactId
from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent
from pycrmkit.organizations import OrganizationId
from pycrmkit.tasks import Task, TaskId, TaskStatus
from pycrmkit.timeline.projections import project_activity_created, project_task_event


def _event(event_type: str, aggregate_type: str, aggregate_id: object) -> DomainEvent:
    return DomainEvent(
        id=EventId(uuid4()),
        type=EventType(event_type),
        schema_version=1,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        occurred_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        actor_id="user-1",
    )


def test_activity_projection_uses_business_occurrence_and_participants() -> None:
    contact = EntityReference("contact", ContactId(uuid4()))
    organization = EntityReference("organization", OrganizationId(uuid4()))
    activity = Activity(
        id=ActivityId(uuid4()),
        created_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        updated_at=datetime(2026, 9, 7, 12, tzinfo=UTC),
        type=ActivityType.MEETING,
        occurred_at=datetime(2026, 9, 6, 9, tzinfo=UTC),
        subject="Quarterly review",
        participants=(ActivityParticipant(contact, is_primary=True),),
        references=(organization,),
    )
    entry = project_activity_created(
        _event("activity.created", "activity", activity.id),
        activity,
    )
    assert entry.occurred_at == activity.occurred_at
    assert entry.references == (contact, organization)
    assert entry.title == "Quarterly review"


def test_completed_task_projection_uses_completed_at() -> None:
    contact = EntityReference("contact", ContactId(uuid4()))
    created = datetime(2026, 9, 7, 9, tzinfo=UTC)
    completed = datetime(2026, 9, 7, 11, tzinfo=UTC)
    task = Task(
        id=TaskId(uuid4()),
        created_at=created,
        updated_at=completed,
        title="Send proposal",
        status=TaskStatus.COMPLETED,
        completed_at=completed,
        references=(contact,),
    )
    entry = project_task_event(
        _event("task.completed", "task", task.id),
        task,
    )
    assert entry.occurred_at == completed
    assert entry.title == "Task completed: Send proposal"
    assert entry.metadata["status"] == "completed"
