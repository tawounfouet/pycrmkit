"""Versioned reusable SavedQuery definitions."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import normalize_entity_kind
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError
from pycrmkit.saved_queries.enums import SavedQueryStatus, SavedQueryVisibility
from pycrmkit.segments.entities import SEGMENTABLE_ENTITY_KINDS
from pycrmkit.segments.expressions import QueryExpression
from pycrmkit.segments.ordering import SortExpression

_SAVED_QUERY_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


class SavedQueryId(UUIDId):
    """Stable identity shared by all revisions of a SavedQuery."""


def normalize_saved_query_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _SAVED_QUERY_KEY.fullmatch(normalized):
        raise ValidationError(
            "saved-query key must be a lowercase slug-like identifier",
            code="saved_query.key.invalid",
            context={"key": value},
        )
    return normalized


def _name(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            "saved-query name is required",
            code="saved_query.name.required",
        )
    if len(normalized) > 200:
        raise ValidationError(
            "saved-query name must be at most 200 characters",
            code="saved_query.name.too_long",
        )
    return normalized


@dataclass(eq=False, slots=True)
class SavedQuery(TimestampedEntity[SavedQueryId]):
    """Reusable, versioned CRM selection semantics."""

    key: str
    name: str
    entity_kind: str
    expression: QueryExpression
    ordering: tuple[SortExpression, ...] = ()
    owner_id: EntityId | None = None
    visibility: SavedQueryVisibility = SavedQueryVisibility.PRIVATE
    status: SavedQueryStatus = SavedQueryStatus.ACTIVE
    revision: int = 1
    metadata: dict[str, object] = field(default_factory=dict)
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.key = normalize_saved_query_key(self.key)
        self.name = _name(self.name)
        self.entity_kind = normalize_entity_kind(self.entity_kind)
        if self.entity_kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported saved-query entity kind",
                code="saved_query.entity_kind.unsupported",
                context={"entity_kind": self.entity_kind},
            )
        self.ordering = tuple(self.ordering)
        self.visibility = SavedQueryVisibility(self.visibility)
        self.status = SavedQueryStatus(self.status)
        self.metadata = dict(self.metadata)
        if self.revision < 1:
            raise ValidationError(
                "saved-query revision must be at least 1",
                code="saved_query.revision.invalid",
            )
        if self.archived_at is not None:
            self.archived_at = as_utc(self.archived_at)
            if self.archived_at < self.created_at:
                raise ValidationError(
                    "saved-query archive timestamp cannot precede creation",
                    code="saved_query.archive.invalid_timestamp",
                )
        if self.status is SavedQueryStatus.ARCHIVED and self.archived_at is None:
            raise ValidationError(
                "archived saved queries require archived_at",
                code="saved_query.archive.timestamp_required",
            )
        if self.status is SavedQueryStatus.ACTIVE and self.archived_at is not None:
            raise ValidationError(
                "active saved queries cannot carry archived_at",
                code="saved_query.archive.status_mismatch",
            )

    def ensure_active(self) -> None:
        if self.status is SavedQueryStatus.ARCHIVED:
            raise InvalidStateError(
                "archived saved query cannot be changed",
                code="saved_query.archived",
                context={"saved_query_id": str(self.id)},
            )


__all__ = ["SavedQuery", "SavedQueryId", "normalize_saved_query_key"]
