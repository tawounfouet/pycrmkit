"""Domain-event projectors for customer-facing timeline history."""

from __future__ import annotations

from pycrmkit.activities import ActivityId
from pycrmkit.activities.repository import ActivityRepository
from pycrmkit.events import DomainEvent
from pycrmkit.tasks import TaskId
from pycrmkit.tasks.repository import TaskRepository
from pycrmkit.timeline.entries import TimelineEntry
from pycrmkit.timeline.projections import project_activity_created, project_task_event
from pycrmkit.timeline.repository import TimelineRepository

_ACTIVITY_EVENTS = frozenset({"activity.created"})
_TASK_EVENTS = frozenset(
    {
        "task.created",
        "task.started",
        "task.completed",
        "task.cancelled",
        "task.reopened",
    }
)
_SUPPORTED_EVENTS = _ACTIVITY_EVENTS | _TASK_EVENTS


class TimelineProjector:
    """Project selected domain events into immutable timeline entries.

    Projection is staged in the same Unit of Work as the source mutation. This
    keeps the timeline read model atomic with domain state while external event
    subscribers continue to receive events only after commit.
    """

    def __init__(
        self,
        repository: TimelineRepository,
        *,
        activities: ActivityRepository,
        tasks: TaskRepository,
    ) -> None:
        self.repository = repository
        self.activities = activities
        self.tasks = tasks

    @staticmethod
    def supports(event_type: object) -> bool:
        return str(event_type).strip().casefold() in _SUPPORTED_EVENTS

    def project(self, event: DomainEvent) -> TimelineEntry | None:
        """Project a supported event; unsupported technical mutations are ignored."""

        event_name = str(event.type)
        entry: TimelineEntry | None
        if event_name in _ACTIVITY_EVENTS:
            activity = self.activities.get(ActivityId.parse(event.aggregate_id))
            entry = project_activity_created(event, activity)
        elif event_name in _TASK_EVENTS:
            task = self.tasks.get(TaskId.parse(event.aggregate_id))
            entry = project_task_event(event, task)
        else:
            return None
        self.repository.append(entry)
        return entry
