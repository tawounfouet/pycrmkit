"""Backend-independent Activity query expressions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pycrmkit.activities.entities import ActivityDirection, ActivityType
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class ActivityQuery:
    """Portable query expression for activity repositories."""

    type: ActivityType | None = None
    participant: EntityReference | None = None
    reference: EntityReference | None = None
    direction: ActivityDirection | None = None
    source: str | None = None
    external_id: str | None = None
    occurred_from: datetime | None = None
    occurred_until: datetime | None = None

    def __post_init__(self) -> None:
        if self.type is not None:
            object.__setattr__(self, "type", ActivityType(self.type))
        if self.direction is not None:
            object.__setattr__(self, "direction", ActivityDirection(self.direction))
        if self.source is not None:
            object.__setattr__(
                self,
                "source",
                " ".join(self.source.strip().split()).casefold(),
            )
        if self.external_id is not None:
            object.__setattr__(
                self,
                "external_id",
                " ".join(self.external_id.strip().split()),
            )
        if self.occurred_from is not None:
            object.__setattr__(self, "occurred_from", as_utc(self.occurred_from))
        if self.occurred_until is not None:
            object.__setattr__(self, "occurred_until", as_utc(self.occurred_until))
        if (
            self.occurred_from is not None
            and self.occurred_until is not None
            and self.occurred_until <= self.occurred_from
        ):
            raise ValidationError(
                "occurred_until must be later than occurred_from",
                code="activity.query.invalid_interval",
            )
