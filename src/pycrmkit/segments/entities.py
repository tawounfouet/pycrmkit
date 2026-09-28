"""Segment definitions and explicit membership records."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.segments.enums import SegmentMode, SegmentStatus
from pycrmkit.segments.expressions import QueryExpression

_SEGMENT_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")
SEGMENTABLE_ENTITY_KINDS: Final[frozenset[str]] = frozenset(
    {"contact", "organization", "lead", "opportunity"}
)


class SegmentId(UUIDId):
    """Strongly typed identifier for a Segment."""


def normalize_segment_key(value: str) -> str:
    """Normalize a stable segment key."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _SEGMENT_KEY.fullmatch(normalized):
        raise ValidationError(
            "segment key must be a lowercase slug-like identifier",
            code="segment.key.invalid",
            context={"key": value},
        )
    return normalized


def _required_name(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError("segment name is required", code="segment.name.required")
    if len(normalized) > 200:
        raise ValidationError(
            "segment name must be at most 200 characters",
            code="segment.name.too_long",
        )
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > 2000:
        raise ValidationError(
            "segment description must be at most 2000 characters",
            code="segment.description.too_long",
        )
    return normalized


@dataclass(eq=False, slots=True)
class Segment(TimestampedEntity[SegmentId]):
    """First-class CRM population definition."""

    key: str
    name: str
    entity_kind: str
    mode: SegmentMode
    description: str | None = None
    status: SegmentStatus = SegmentStatus.ACTIVE
    query: QueryExpression | None = None
    saved_query_id: UUIDId | None = None
    saved_query_revision: int | None = None
    owner_id: EntityId | None = None
    revision: int = 1
    metadata: dict[str, object] = field(default_factory=dict)
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.key = normalize_segment_key(self.key)
        self.name = _required_name(self.name)
        self.entity_kind = normalize_entity_kind(self.entity_kind)
        if self.entity_kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": self.entity_kind},
            )
        try:
            self.mode = SegmentMode(self.mode)
            self.status = SegmentStatus(self.status)
        except ValueError as exc:
            raise ValidationError(
                "invalid segment enum value",
                code="segment.mode.invalid",
            ) from exc
        self.description = _optional_text(self.description)
        self.metadata = dict(self.metadata)
        if self.revision < 1:
            raise ValidationError(
                "segment revision must be at least 1",
                code="segment.revision.invalid",
            )
        if self.mode is SegmentMode.DYNAMIC and self.query is None:
            raise ValidationError(
                "dynamic segments require a query expression",
                code="segment.query.required",
            )
        if (self.saved_query_id is None) != (self.saved_query_revision is None):
            raise ValidationError(
                "saved-query binding requires both id and revision",
                code="segment.saved_query.invalid_binding",
            )
        if self.saved_query_revision is not None and self.saved_query_revision < 1:
            raise ValidationError(
                "saved-query revision must be at least 1",
                code="segment.saved_query.invalid_revision",
            )
        if self.saved_query_id is not None and self.mode is not SegmentMode.DYNAMIC:
            raise ValidationError(
                "only dynamic segments may bind to a SavedQuery",
                code="segment.saved_query.not_allowed",
            )
        if self.mode is not SegmentMode.DYNAMIC and self.query is not None:
            raise ValidationError(
                "only dynamic segments may own a query expression",
                code="segment.query.not_allowed",
            )
        if self.archived_at is not None:
            self.archived_at = as_utc(self.archived_at)
            if self.archived_at < self.created_at:
                raise ValidationError(
                    "segment archive timestamp cannot precede creation",
                    code="segment.archive.invalid_timestamp",
                )
        if self.status is SegmentStatus.ARCHIVED and self.archived_at is None:
            raise ValidationError(
                "archived segments require archived_at",
                code="segment.archive.timestamp_required",
            )
        if self.status is SegmentStatus.ACTIVE and self.archived_at is not None:
            raise ValidationError(
                "active segments cannot carry archived_at",
                code="segment.archive.status_mismatch",
            )

    def archive(self, at: datetime) -> None:
        """Archive the segment idempotently."""

        timestamp = as_utc(at)
        if timestamp < self.created_at:
            raise ValidationError(
                "segment archive timestamp cannot precede creation",
                code="segment.archive.invalid_timestamp",
            )
        if self.status is SegmentStatus.ARCHIVED:
            return
        self.status = SegmentStatus.ARCHIVED
        self.archived_at = timestamp
        self.updated_at = timestamp
        self.revision += 1

    def ensure_active(self) -> None:
        if self.status is SegmentStatus.ARCHIVED:
            raise InvalidStateError(
                "archived segment cannot be mutated",
                code="segment.archived",
                context={"segment_id": str(self.id)},
            )

    def ensure_membership_writable(self) -> None:
        self.ensure_active()
        if self.mode is SegmentMode.DYNAMIC:
            raise InvalidStateError(
                "dynamic segment membership is derived",
                code="segment.membership.not_writable",
                context={"segment_id": str(self.id)},
            )
        if self.mode is SegmentMode.SNAPSHOT:
            raise InvalidStateError(
                "snapshot segment membership is immutable",
                code="segment.snapshot.immutable",
                context={"segment_id": str(self.id)},
            )


@dataclass(frozen=True, slots=True)
class SegmentMember:
    """Stored membership record for a Static or Snapshot Segment."""

    segment_id: SegmentId
    entity: EntityReference
    added_at: datetime
    source: str = "manual"
    actor_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "added_at", as_utc(self.added_at))
        source = " ".join(
            unicodedata.normalize("NFKC", self.source).strip().split()
        ).casefold()
        if not source:
            raise ValidationError(
                "segment member source is required",
                code="segment.member.source.required",
            )
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "metadata", dict(self.metadata))


__all__ = [
    "SEGMENTABLE_ENTITY_KINDS",
    "Segment",
    "SegmentId",
    "SegmentMember",
    "normalize_segment_key",
]
