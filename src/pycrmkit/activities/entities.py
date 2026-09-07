"""Activity aggregate root."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from pycrmkit.activities.participants import ActivityParticipant
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError


class ActivityId(UUIDId):
    """Strongly typed identifier for an Activity."""


class ActivityType(StrEnum):
    """Base interaction types owned by the CRM Activity domain."""

    EMAIL = "email"
    CALL = "call"
    MEETING = "meeting"
    NOTE = "note"
    MESSAGE = "message"
    DOCUMENT = "document"
    EVENT = "event"
    CUSTOM = "custom"


class ActivityDirection(StrEnum):
    """Optional direction for directional interactions."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


def _normalize_optional_text(
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
            code=f"activity.{field_name}.too_long",
        )
    return normalized


def _validate_participants(participants: tuple[ActivityParticipant, ...]) -> None:
    references = [participant.reference for participant in participants]
    if len(set(references)) != len(references):
        raise ValidationError(
            "an entity can participate at most once in one activity",
            code="activity.participant.duplicate",
        )
    if sum(participant.is_primary for participant in participants) > 1:
        raise ValidationError(
            "an activity can have at most one primary participant",
            code="activity.participant.multiple_primary",
        )


def _validate_references(references: tuple[EntityReference, ...]) -> None:
    if len(set(references)) != len(references):
        raise ValidationError(
            "activity references must be unique",
            code="activity.reference.duplicate",
        )


@dataclass(eq=False, slots=True)
class Activity(TimestampedEntity[ActivityId]):
    """Generic CRM interaction record independent from communication providers."""

    type: ActivityType
    occurred_at: datetime
    subject: str | None = None
    description: str | None = None
    direction: ActivityDirection | None = None
    duration_seconds: int | None = None
    participants: tuple[ActivityParticipant, ...] = ()
    references: tuple[EntityReference, ...] = ()
    source: str | None = None
    external_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.type = ActivityType(self.type)
        self.occurred_at = as_utc(self.occurred_at)
        self.subject = _normalize_optional_text(
            self.subject,
            field_name="subject",
            max_length=300,
        )
        if self.description is not None:
            description = unicodedata.normalize("NFKC", self.description).strip()
            if len(description) > 10_000:
                raise ValidationError(
                    "description must be at most 10000 characters",
                    code="activity.description.too_long",
                )
            self.description = description or None
        if self.direction is not None:
            self.direction = ActivityDirection(self.direction)
        if self.duration_seconds is not None:
            if type(self.duration_seconds) is not int or self.duration_seconds < 0:
                raise ValidationError(
                    "duration_seconds must be a non-negative integer",
                    code="activity.duration.invalid",
                )
        self.participants = tuple(self.participants)
        self.references = tuple(self.references)
        self.source = _normalize_optional_text(
            self.source,
            field_name="source",
            max_length=120,
        )
        self.external_id = _normalize_optional_text(
            self.external_id,
            field_name="external_id",
            max_length=255,
        )
        self.metadata = dict(self.metadata)
        _validate_participants(self.participants)
        _validate_references(self.references)
        if not (
            self.subject
            or self.description
            or self.participants
            or self.references
            or self.external_id
        ):
            raise ValidationError(
                "activity must carry meaningful interaction context",
                code="activity.context.required",
            )
