"""Application service for CRM Campaign metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeVar

from pycrmkit.campaigns.dto import CampaignUpdate, UnsetType
from pycrmkit.campaigns.entities import Campaign, CampaignId
from pycrmkit.campaigns.enums import CampaignStatus
from pycrmkit.campaigns.queries import CampaignQuery
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.core.ids import EntityId, IDFactory, UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import ConflictError

T = TypeVar("T")


@dataclass(slots=True)
class CampaignService:
    """Framework-independent Campaign metadata lifecycle."""

    repository: CampaignRepository
    id_factory: IDFactory = field(default_factory=UUID4Factory)
    clock: Clock = field(default_factory=SystemClock)

    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Campaign:
        now = self.clock.now()
        campaign = Campaign(
            id=self.id_factory.new(CampaignId),
            created_at=now,
            updated_at=now,
            key=key,
            name=name,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            owner_id=owner_id,
            metadata=dict(metadata or {}),
        )
        self.repository.save(campaign)
        return campaign

    def get(self, campaign_id: CampaignId) -> Campaign:
        return self.repository.get(campaign_id)

    def list(
        self,
        query: CampaignQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Campaign]:
        return self.repository.search(
            query or CampaignQuery(),
            page or OffsetPageRequest(),
        )

    def update(
        self,
        campaign_id: CampaignId,
        changes: CampaignUpdate,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        current = self.repository.get(campaign_id)
        current.ensure_mutable()
        self._check_revision(current, expected_revision)
        if not self._has_changes(changes):
            return current
        revised = Campaign(
            id=current.id,
            created_at=current.created_at,
            updated_at=self.clock.now(),
            key=current.key,
            name=self._value(changes.name, current.name),
            description=self._value(changes.description, current.description),
            status=current.status,
            starts_at=self._value(changes.starts_at, current.starts_at),
            ends_at=self._value(changes.ends_at, current.ends_at),
            owner_id=self._value(changes.owner_id, current.owner_id),
            revision=current.revision + 1,
            metadata=dict(self._value(changes.metadata, current.metadata)),
            archived_at=current.archived_at,
        )
        self.repository.save(revised)
        return revised

    def activate(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        campaign = self.repository.get(campaign_id)
        self._check_revision(campaign, expected_revision)
        before = campaign.revision
        campaign.activate(self.clock.now())
        if campaign.revision != before:
            self.repository.save(campaign)
        return campaign

    def complete(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        campaign = self.repository.get(campaign_id)
        self._check_revision(campaign, expected_revision)
        before = campaign.revision
        campaign.complete(self.clock.now())
        if campaign.revision != before:
            self.repository.save(campaign)
        return campaign

    def archive(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        campaign = self.repository.get(campaign_id)
        self._check_revision(campaign, expected_revision)
        before = campaign.revision
        campaign.archive(self.clock.now())
        if campaign.revision != before:
            self.repository.save(campaign)
        return campaign

    @staticmethod
    def _check_revision(
        campaign: Campaign,
        expected_revision: int | None,
    ) -> None:
        if expected_revision is not None and campaign.revision != expected_revision:
            raise ConflictError(
                "campaign revision has changed",
                code="campaign.revision.conflict",
                context={
                    "expected": expected_revision,
                    "actual": campaign.revision,
                },
            )

    @staticmethod
    def _has_changes(changes: CampaignUpdate) -> bool:
        return any(
            not isinstance(getattr(changes, name), UnsetType)
            for name in (
                "name",
                "description",
                "starts_at",
                "ends_at",
                "owner_id",
                "metadata",
            )
        )

    @staticmethod
    def _value(value: T | UnsetType, current: T) -> T:
        return current if isinstance(value, UnsetType) else value


__all__ = ["CampaignService"]
