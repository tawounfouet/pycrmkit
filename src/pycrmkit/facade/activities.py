"""Activities facade namespace."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from pycrmkit.activities import (
    Activity,
    ActivityDirection,
    ActivityId,
    ActivityParticipant,
    ActivityQuery,
    ActivityService,
    ActivityType,
    ActivityUpdate,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.facade._runtime import CRMRuntime, present_fields, revision_fields


class ActivitiesAPI:
    """Transactional facade namespace for CRM interaction history."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def log(
        self,
        *,
        type: ActivityType | str,
        occurred_at: datetime | None = None,
        subject: str | None = None,
        description: str | None = None,
        direction: ActivityDirection | str | None = None,
        duration_seconds: int | None = None,
        participants: Sequence[ActivityParticipant] = (),
        references: Sequence[EntityReference] = (),
        source: str | None = None,
        external_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Activity:
        with self._runtime.uow_factory() as uow:
            activity = ActivityService(
                uow.activities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).log(
                type=type,
                occurred_at=occurred_at,
                subject=subject,
                description=description,
                direction=direction,
                duration_seconds=duration_seconds,
                participants=participants,
                references=references,
                source=source,
                external_id=external_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="activity.created",
                aggregate_type="activity",
                aggregate_id=activity.id,
                changes={
                    "fields": present_fields(
                        {
                            "type": type,
                            "occurred_at": occurred_at,
                            "subject": subject,
                            "description": description,
                            "direction": direction,
                            "duration_seconds": duration_seconds,
                            "participants": tuple(participants),
                            "references": tuple(references),
                            "source": source,
                            "external_id": external_id,
                            "metadata": metadata or {},
                        }
                    )
                },
                payload={"activity_type": activity.type.value},
            )
            uow.commit()
            return activity

    def get(self, activity_id: ActivityId) -> Activity:
        with self._runtime.uow_factory() as uow:
            return uow.activities.get(activity_id)

    def update(self, activity_id: ActivityId, changes: ActivityUpdate) -> Activity:
        with self._runtime.uow_factory() as uow:
            activity = ActivityService(
                uow.activities,
                id_factory=self._runtime.id_factory,
                clock=self._runtime.clock,
            ).update(activity_id, changes)
            self._runtime.record_change(
                uow,
                event_type="activity.updated",
                aggregate_type="activity",
                aggregate_id=activity.id,
                changes={"fields": revision_fields(changes)},
                payload={"activity_type": activity.type.value},
            )
            uow.commit()
            return activity

    def list(
        self,
        query: ActivityQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Activity]:
        with self._runtime.uow_factory() as uow:
            return ActivityService(uow.activities).list(query, page)
