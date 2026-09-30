"""Persistence contract for Campaign metadata."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.entities import Campaign, CampaignId
from pycrmkit.campaigns.queries import CampaignQuery
from pycrmkit.core.pagination import OffsetPageRequest, Page


@runtime_checkable
class CampaignRepository(Protocol):
    """Backend-neutral Campaign repository."""

    def get(self, campaign_id: CampaignId) -> Campaign:
        """Return one Campaign or raise NotFoundError."""

    def find(self, campaign_id: CampaignId) -> Campaign | None:
        """Return one Campaign or None."""

    def find_by_key(self, key: str) -> Campaign | None:
        """Return one Campaign by normalized key or None."""

    def save(self, campaign: Campaign) -> None:
        """Persist current Campaign state."""

    def search(
        self,
        query: CampaignQuery,
        page: OffsetPageRequest,
    ) -> Page[Campaign]:
        """Search Campaigns with deterministic pagination."""


__all__ = ["CampaignRepository"]
