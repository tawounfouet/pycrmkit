"""Immutable customer-facing timeline entries."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.core.events import EventId, EventType
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.json import freeze_json_mapping, thaw_json_mapping
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError


class TimelineEntryId(UUIDId):
    """Stable identifier for one projected timeline occurrence."""


class TimelineEntryKind(StrEnum):
    """Source domain represented by a timeline entry."""

    ACTIVITY = "activity"
    TASK = "task"


def _required_text(value: str, *, field_name: str, max_length: int) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            f"{field_name} is required",
            code=f"timeline.{field_name}.required",
        )
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"timeline.{field_name}.too_long",
        )
    return normalized


def _optional_text(
    value: str | None,
    *,
    field_name: str,
    max_length: int,
) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"timeline.{field_name}.too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """Read-oriented projection of one meaningful CRM history occurrence.

    Timeline entries are immutable projections. ``source_event_id`` provides the
    idempotency key for replaying the originating DomainEvent while ``entity``
    points to the source aggregate and ``references`` identify related CRM
    entities such as contacts or organizations.
    """

    id: TimelineEntryId
    kind: TimelineEntryKind
    event_type: EventType
    source_event_id: EventId
    entity: EntityReference
    occurred_at: datetime
    title: str
    summary: str | None = None
    references: tuple[EntityReference, ...] = ()
    actor_id: str | None = None
    correlation_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, TimelineEntryId):
            raise ValidationError(
                "timeline entry id must be a TimelineEntryId",
                code="timeline.id.invalid",
            )
        if not isinstance(self.source_event_id, EventId):
            raise ValidationError(
                "timeline source_event_id must be an EventId",
                code="timeline.source_event_id.invalid",
            )
        if self.id.value != self.source_event_id.value:
            raise ValidationError(
                "timeline entry id must match source event id",
                code="timeline.id.event_mismatch",
            )
        object.__setattr__(self, "kind", TimelineEntryKind(self.kind))
        object.__setattr__(self, "event_type", EventType.parse(self.event_type))
        if not isinstance(self.entity, EntityReference):
            raise ValidationError(
                "timeline entity must be an EntityReference",
                code="timeline.entity.invalid",
            )
        object.__setattr__(self, "occurred_at", as_utc(self.occurred_at))
        object.__setattr__(
            self,
            "title",
            _required_text(self.title, field_name="title", max_length=300),
        )
        object.__setattr__(
            self,
            "summary",
            _optional_text(self.summary, field_name="summary", max_length=2_000),
        )
        references = tuple(dict.fromkeys(self.references))
        if any(not isinstance(reference, EntityReference) for reference in references):
            raise ValidationError(
                "timeline references must be EntityReference values",
                code="timeline.reference.invalid",
            )
        object.__setattr__(self, "references", references)
        object.__setattr__(
            self,
            "actor_id",
            _optional_text(self.actor_id, field_name="actor_id", max_length=255),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _optional_text(
                self.correlation_id,
                field_name="correlation_id",
                max_length=255,
            ),
        )
        object.__setattr__(self, "metadata", freeze_json_mapping(self.metadata))

    def __deepcopy__(self, memo: dict[int, object]) -> TimelineEntry:
        """Immutable entries can safely be shared across MemoryStore snapshots."""

        del memo
        return self

    def to_dict(self) -> dict[str, object]:
        """Serialize the public timeline projection to JSON-compatible primitives."""

        return {
            "id": str(self.id),
            "kind": self.kind.value,
            "event_type": str(self.event_type),
            "source_event_id": str(self.source_event_id),
            "entity": {"kind": self.entity.kind, "id": str(self.entity.id)},
            "occurred_at": self.occurred_at.isoformat(),
            "title": self.title,
            "summary": self.summary,
            "references": [
                {"kind": reference.kind, "id": str(reference.id)}
                for reference in self.references
            ],
            "actor_id": self.actor_id,
            "correlation_id": self.correlation_id,
            "metadata": thaw_json_mapping(self.metadata),
        }
