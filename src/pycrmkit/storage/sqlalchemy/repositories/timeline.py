"""SQLAlchemy TimelineRepository implementation."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from pycrmkit.core.events import EventType
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import DuplicateError, NotFoundError, ValidationError
from pycrmkit.storage.sqlalchemy.mappers import (
    timeline_from_model,
    timeline_to_model,
)
from pycrmkit.storage.sqlalchemy.models.timeline import (
    TimelineEntryModel,
    TimelineReferenceModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models
from pycrmkit.timeline import TimelineEntry, TimelineEntryId, TimelineEntryKind


class SQLAlchemyTimelineRepository:
    """Immutable, idempotent SQLAlchemy timeline projection store."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entry_id: TimelineEntryId) -> TimelineEntry:
        entry = self.find(entry_id)
        if entry is None:
            raise NotFoundError(
                "timeline entry not found",
                code="timeline.not_found",
                context={"timeline_entry_id": str(entry_id)},
            )
        return entry

    def find(
        self,
        entry_id: TimelineEntryId,
    ) -> TimelineEntry | None:
        model = self.session.get(
            TimelineEntryModel,
            str(entry_id),
        )
        return None if model is None else self._hydrate(model)

    def append(self, entry: TimelineEntry) -> None:
        existing = self.find(entry.id)
        if existing is not None:
            if existing != entry:
                raise DuplicateError(
                    "timeline entry id already contains different projected content",
                    code="timeline.projection.conflict",
                    context={
                        "timeline_entry_id": str(entry.id)
                    },
                )
            return
        self.session.add(timeline_to_model(entry))
        self.session.add_all(
            [
                TimelineReferenceModel(
                    entry_id=str(entry.id),
                    position=position,
                    entity_kind=reference.kind,
                    entity_id=str(reference.id),
                )
                for position, reference in enumerate(
                    entry.references
                )
            ]
        )

    def list_for_reference(
        self,
        reference: EntityReference,
        page: OffsetPageRequest,
        *,
        kind: TimelineEntryKind | None = None,
        event_type: EventType | str | None = None,
        occurred_from: datetime | None = None,
        occurred_until: datetime | None = None,
    ) -> Page[TimelineEntry]:
        lower = (
            as_utc(occurred_from)
            if occurred_from is not None
            else None
        )
        upper = (
            as_utc(occurred_until)
            if occurred_until is not None
            else None
        )
        if (
            lower is not None
            and upper is not None
            and upper <= lower
        ):
            raise ValidationError(
                "occurred_until must be later than occurred_from",
                code="timeline.query.invalid_interval",
            )

        statement = select(TimelineEntryModel).where(
            exists(
                select(TimelineReferenceModel.id).where(
                    TimelineReferenceModel.entry_id
                    == TimelineEntryModel.id,
                    TimelineReferenceModel.entity_kind
                    == reference.kind,
                    TimelineReferenceModel.entity_id
                    == str(reference.id),
                )
            )
        )
        if kind is not None:
            statement = statement.where(
                TimelineEntryModel.kind
                == TimelineEntryKind(kind).value
            )
        if event_type is not None:
            statement = statement.where(
                TimelineEntryModel.event_type
                == str(EventType.parse(event_type))
            )
        if lower is not None:
            statement = statement.where(
                TimelineEntryModel.occurred_at >= lower
            )
        if upper is not None:
            statement = statement.where(
                TimelineEntryModel.occurred_at < upper
            )
        statement = statement.order_by(
            TimelineEntryModel.occurred_at.desc(),
            TimelineEntryModel.kind.asc(),
            TimelineEntryModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            self._hydrate,
        )

    def _hydrate(
        self,
        model: TimelineEntryModel,
    ) -> TimelineEntry:
        references = list(
            self.session.scalars(
                select(TimelineReferenceModel)
                .where(
                    TimelineReferenceModel.entry_id
                    == model.id
                )
                .order_by(
                    TimelineReferenceModel.position.asc(),
                    TimelineReferenceModel.id.asc(),
                )
            )
        )
        return timeline_from_model(
            model,
            references,
        )
