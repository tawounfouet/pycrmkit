"""Campaign definitions and lifecycle semantics."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.core.entities import TimestampedEntity
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import InvalidStateError, ValidationError

_CAMPAIGN_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,119}$")


class CampaignId(UUIDId):
    """Strongly typed identifier for a Campaign."""


def normalize_campaign_key(value: str) -> str:
    """Normalize a stable Campaign key."""

    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not _CAMPAIGN_KEY.fullmatch(normalized):
        raise ValidationError(
            "campaign key must be a lowercase slug-like identifier",
            code="campaign.key.invalid",
            context={"key": value},
        )
    return normalized


def _required_name(value: str) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        raise ValidationError(
            "campaign name is required",
            code="campaign.name.required",
        )
    if len(normalized) > 200:
        raise ValidationError(
            "campaign name must be at most 200 characters",
            code="campaign.name.too_long",
        )
    return normalized


def _optional_description(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not normalized:
        return None
    if len(normalized) > 2000:
        raise ValidationError(
            "campaign description must be at most 2000 characters",
            code="campaign.description.too_long",
        )
    return normalized


@dataclass(eq=False, slots=True)
class Campaign(TimestampedEntity[CampaignId]):
    """CRM-adjacent Campaign metadata without delivery/orchestration concerns."""

    key: str
    name: str
    description: str | None = None
    status: CampaignStatus = CampaignStatus.DRAFT
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    owner_id: EntityId | None = None
    revision: int = 1
    metadata: dict[str, object] = field(default_factory=dict)
    archived_at: datetime | None = None

    def __post_init__(self) -> None:
        TimestampedEntity.__post_init__(self)
        self.key = normalize_campaign_key(self.key)
        self.name = _required_name(self.name)
        self.description = _optional_description(self.description)
        try:
            self.status = CampaignStatus(self.status)
        except ValueError as exc:
            raise ValidationError(
                "invalid campaign status",
                code="campaign.status.invalid",
            ) from exc
        self.starts_at = as_utc(self.starts_at) if self.starts_at is not None else None
        self.ends_at = as_utc(self.ends_at) if self.ends_at is not None else None
        self.archived_at = (
            as_utc(self.archived_at) if self.archived_at is not None else None
        )
        self.metadata = dict(self.metadata)
        if self.revision < 1:
            raise ValidationError(
                "campaign revision must be at least 1",
                code="campaign.revision.invalid",
            )
        self._validate_schedule()
        if self.archived_at is not None and self.archived_at < self.created_at:
            raise ValidationError(
                "campaign archive timestamp cannot precede creation",
                code="campaign.archive.invalid_timestamp",
            )
        if self.status is CampaignStatus.ARCHIVED and self.archived_at is None:
            raise ValidationError(
                "archived campaigns require archived_at",
                code="campaign.archive.timestamp_required",
            )
        if self.status is not CampaignStatus.ARCHIVED and self.archived_at is not None:
            raise ValidationError(
                "non-archived campaigns cannot carry archived_at",
                code="campaign.archive.status_mismatch",
            )

    def ensure_mutable(self) -> None:
        """Reject metadata mutation after archival."""

        if self.status is CampaignStatus.ARCHIVED:
            raise InvalidStateError(
                "archived campaign cannot be mutated",
                code="campaign.archived",
                context={"campaign_id": str(self.id)},
            )

    def activate(self, at: datetime) -> None:
        """Activate a draft Campaign, idempotently for already-active state."""

        self.ensure_mutable()
        if self.status is CampaignStatus.ACTIVE:
            return
        if self.status is not CampaignStatus.DRAFT:
            raise InvalidStateError(
                "only draft campaigns can be activated",
                code="campaign.activate.invalid_state",
                context={"status": self.status.value},
            )
        timestamp = as_utc(at)
        self.status = CampaignStatus.ACTIVE
        self.updated_at = timestamp
        self.revision += 1

    def complete(self, at: datetime) -> None:
        """Complete an active Campaign, idempotently for completed state."""

        self.ensure_mutable()
        if self.status is CampaignStatus.COMPLETED:
            return
        if self.status is not CampaignStatus.ACTIVE:
            raise InvalidStateError(
                "only active campaigns can be completed",
                code="campaign.complete.invalid_state",
                context={"status": self.status.value},
            )
        timestamp = as_utc(at)
        self.status = CampaignStatus.COMPLETED
        self.updated_at = timestamp
        self.revision += 1

    def archive(self, at: datetime) -> None:
        """Archive the Campaign idempotently."""

        timestamp = as_utc(at)
        if timestamp < self.created_at:
            raise ValidationError(
                "campaign archive timestamp cannot precede creation",
                code="campaign.archive.invalid_timestamp",
            )
        if self.status is CampaignStatus.ARCHIVED:
            return
        self.status = CampaignStatus.ARCHIVED
        self.archived_at = timestamp
        self.updated_at = timestamp
        self.revision += 1

    def _validate_schedule(self) -> None:
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at < self.starts_at
        ):
            raise ValidationError(
                "campaign ends_at cannot precede starts_at",
                code="campaign.schedule.invalid",
            )


__all__ = ["Campaign", "CampaignId", "normalize_campaign_key"]
