"""Pure projection helpers from domain state/events into timeline entries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from pycrmkit.activities import Activity
from pycrmkit.communication import CommunicationIntent, CommunicationRecord
from pycrmkit.core.events import EventType
from pycrmkit.core.references import EntityReference
from pycrmkit.events import DomainEvent
from pycrmkit.tasks import Task
from pycrmkit.timeline.entries import TimelineEntry, TimelineEntryId, TimelineEntryKind


def _entry_id(event: DomainEvent) -> TimelineEntryId:
    return TimelineEntryId(event.id.value)


def _unique_references(values: Iterable[EntityReference]) -> tuple[EntityReference, ...]:
    return tuple(dict.fromkeys(values))


def _task_occurred_at(event: DomainEvent, task: Task) -> datetime:
    event_name = str(event.type)
    if event_name == "task.created":
        return task.created_at
    if event_name == "task.started" and task.started_at is not None:
        return task.started_at
    if event_name == "task.completed" and task.completed_at is not None:
        return task.completed_at
    if event_name == "task.cancelled" and task.cancelled_at is not None:
        return task.cancelled_at
    return task.updated_at


def _task_title(event_type: EventType, task: Task) -> str:
    action = str(event_type).partition(".")[2]
    labels = {
        "created": "Task created",
        "started": "Task started",
        "completed": "Task completed",
        "cancelled": "Task cancelled",
        "reopened": "Task reopened",
    }
    return f"{labels.get(action, 'Task updated')}: {task.title}"


def project_activity_created(event: DomainEvent, activity: Activity) -> TimelineEntry:
    """Project an ``activity.created`` event using business occurrence time."""

    references = _unique_references(
        [
            *(participant.reference for participant in activity.participants),
            *activity.references,
        ]
    )
    title = activity.subject or f"{activity.type.value.capitalize()} activity"
    metadata: Mapping[str, object] = {
        "activity_type": activity.type.value,
        "direction": activity.direction.value if activity.direction is not None else None,
        "duration_seconds": activity.duration_seconds,
        "source": activity.source,
    }
    return TimelineEntry(
        id=_entry_id(event),
        kind=TimelineEntryKind.ACTIVITY,
        event_type=event.type,
        source_event_id=event.id,
        entity=EntityReference(kind="activity", id=activity.id),
        occurred_at=activity.occurred_at,
        title=title,
        summary=activity.description,
        references=references,
        actor_id=event.actor_id,
        correlation_id=event.correlation_id,
        metadata=metadata,
    )


def project_task_event(event: DomainEvent, task: Task) -> TimelineEntry:
    """Project one meaningful Task lifecycle event."""

    metadata: Mapping[str, object] = {
        "status": task.status.value,
        "priority": task.priority.name.lower(),
        "due_at": task.due_at.isoformat() if task.due_at is not None else None,
        "owner_id": task.owner_id,
        "assignee_id": task.assignee_id,
        "source": task.source,
    }
    return TimelineEntry(
        id=_entry_id(event),
        kind=TimelineEntryKind.TASK,
        event_type=event.type,
        source_event_id=event.id,
        entity=EntityReference(kind="task", id=task.id),
        occurred_at=_task_occurred_at(event, task),
        title=_task_title(event.type, task),
        summary=task.description,
        references=task.references,
        actor_id=event.actor_id,
        correlation_id=event.correlation_id,
        metadata=metadata,
    )

def _email_business_time(event: DomainEvent, fallback: datetime) -> datetime:
    raw = event.payload.get("business_occurred_at")
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return fallback

def _email_title(event: DomainEvent, subject: str | None) -> str:
    action = str(event.type).partition(".")[2]
    labels = {
        "queued":"Email queued", "sent":"Email sent", "delivered":"Email delivered",
        "opened":"Email opened", "clicked":"Email clicked", "bounced":"Email bounced",
        "failed":"Email failed",
    }
    return f"{labels.get(action, 'Email event')}: {subject}" if subject else labels.get(action, "Email event")

def project_email_queued(event: DomainEvent, intent: CommunicationIntent) -> TimelineEntry:
    return TimelineEntry(
        id=_entry_id(event), kind=TimelineEntryKind.COMMUNICATION, event_type=event.type,
        source_event_id=event.id, entity=EntityReference("communication_intent", intent.id),
        occurred_at=_email_business_time(event, intent.queued_at or intent.updated_at),
        title=_email_title(event, intent.content.subject), references=intent.references,
        actor_id=event.actor_id, correlation_id=event.correlation_id,
        metadata={"delivery_status":"queued"},
    )

def project_email_record_event(event: DomainEvent, record: CommunicationRecord) -> TimelineEntry:
    return TimelineEntry(
        id=_entry_id(event), kind=TimelineEntryKind.COMMUNICATION, event_type=event.type,
        source_event_id=event.id, entity=EntityReference("communication_record", record.id),
        occurred_at=_email_business_time(event, record.last_delivery_event_at or record.occurred_at),
        title=_email_title(event, record.subject), references=record.references,
        actor_id=event.actor_id, correlation_id=event.correlation_id,
        metadata={"delivery_status":str(event.type).partition(".")[2], "provider":event.payload.get("provider")},
    )
