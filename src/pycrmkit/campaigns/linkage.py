"""Campaign attribution references and communication linkage."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from pycrmkit.campaigns.entities import CampaignId
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import SEGMENTABLE_ENTITY_KINDS


def _normalized_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    normalized = " ".join(
        unicodedata.normalize("NFKC", value).strip().split()
    ).casefold()
    if not normalized:
        raise ValidationError(
            f"{field_name} is required",
            code=f"campaign.{field_name}.required",
        )
    if len(normalized) > max_length:
        raise ValidationError(
            f"{field_name} must be at most {max_length} characters",
            code=f"campaign.{field_name}.too_long",
        )
    return normalized


def _optional_external_ref(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).strip()
    if not normalized:
        return None
    if len(normalized) > 512:
        raise ValidationError(
            "external_ref must be at most 512 characters",
            code="campaign.attribution.external_ref.too_long",
        )
    return normalized


@dataclass(frozen=True, slots=True)
class CampaignAttributionReference:
    """Traceable source reference from one Campaign to one CRM entity."""

    campaign_id: CampaignId
    target: EntityReference
    source: str
    recorded_at: datetime
    external_ref: str | None = None
    actor_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.target.kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported campaign attribution target kind",
                code="campaign.attribution.target_kind.unsupported",
                context={"entity_kind": self.target.kind},
            )
        object.__setattr__(
            self,
            "source",
            _normalized_text(
                self.source,
                field_name="attribution.source",
                max_length=120,
            ),
        )
        object.__setattr__(self, "recorded_at", as_utc(self.recorded_at))
        object.__setattr__(self, "external_ref", _optional_external_ref(self.external_ref))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class CampaignCommunicationLink:
    """Provider-neutral link to an existing CRM CommunicationRecord."""

    campaign_id: CampaignId
    communication_id: CommunicationRecordId
    linked_at: datetime
    role: str = "touchpoint"
    actor_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "linked_at", as_utc(self.linked_at))
        object.__setattr__(
            self,
            "role",
            _normalized_text(
                self.role,
                field_name="communication_link.role",
                max_length=120,
            ),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))


__all__ = ["CampaignAttributionReference", "CampaignCommunicationLink"]
