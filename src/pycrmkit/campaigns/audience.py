"""Campaign audience records and source provenance."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from pycrmkit.campaigns.entities import CampaignId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import SEGMENTABLE_ENTITY_KINDS, SegmentId


def _source(value: str) -> str:
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().split()
    ).casefold()
    if not normalized:
        raise ValidationError(
            "campaign member source is required",
            code="campaign.member.source.required",
        )
    if len(normalized) > 120:
        raise ValidationError(
            "campaign member source must be at most 120 characters",
            code="campaign.member.source.too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CampaignMember:
    """Explicit Campaign audience member independent from Segment sources."""

    campaign_id: CampaignId
    entity: EntityReference
    added_at: datetime
    source: str = "manual"
    actor_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.entity.kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported campaign member entity kind",
                code="campaign.member.kind.unsupported",
                context={"entity_kind": self.entity.kind},
            )
        object.__setattr__(self, "added_at", as_utc(self.added_at))
        object.__setattr__(self, "source", _source(self.source))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class CampaignSegmentSource:
    """Materialized Segment source attached to one Campaign audience."""

    campaign_id: CampaignId
    segment_id: SegmentId
    segment_revision: int
    entity_kind: str
    attached_at: datetime
    captured_at: datetime
    member_count: int
    actor_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = normalize_entity_kind(self.entity_kind)
        if kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported campaign segment source entity kind",
                code="campaign.segment_source.kind.unsupported",
                context={"entity_kind": kind},
            )
        object.__setattr__(self, "entity_kind", kind)
        object.__setattr__(self, "attached_at", as_utc(self.attached_at))
        object.__setattr__(self, "captured_at", as_utc(self.captured_at))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.segment_revision < 1:
            raise ValidationError(
                "segment source revision must be at least 1",
                code="campaign.segment_source.revision.invalid",
            )
        if self.member_count < 0:
            raise ValidationError(
                "segment source member_count cannot be negative",
                code="campaign.segment_source.member_count.invalid",
            )
        if self.captured_at < self.attached_at:
            raise ValidationError(
                "segment source capture cannot precede attachment",
                code="campaign.segment_source.capture.invalid_timestamp",
            )


__all__ = ["CampaignMember", "CampaignSegmentSource"]
