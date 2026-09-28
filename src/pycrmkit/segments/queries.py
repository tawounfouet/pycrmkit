"""Backend-independent Segment query objects."""

from __future__ import annotations

from dataclasses import dataclass

from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import normalize_entity_kind
from pycrmkit.segments.enums import SegmentMode, SegmentStatus


@dataclass(frozen=True, slots=True)
class SegmentQuery:
    """Portable filters for Segment repositories."""

    status: SegmentStatus | None = None
    mode: SegmentMode | None = None
    entity_kind: str | None = None
    owner_id: EntityId | None = None
    include_archived: bool = False

    def __post_init__(self) -> None:
        if self.status is not None:
            object.__setattr__(self, "status", SegmentStatus(self.status))
        if self.mode is not None:
            object.__setattr__(self, "mode", SegmentMode(self.mode))
        if self.entity_kind is not None:
            object.__setattr__(
                self,
                "entity_kind",
                normalize_entity_kind(self.entity_kind),
            )


__all__ = ["SegmentQuery"]
