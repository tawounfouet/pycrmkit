"""In-memory repository for Campaign metadata."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignQuery,
    CampaignStatus,
    normalize_campaign_key,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.storage.memory._state import _MemoryState


class MemoryCampaignRepository:
    """Copy-isolated in-memory Campaign repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, campaign_id: CampaignId) -> Campaign:
        campaign = self.find(campaign_id)
        if campaign is None:
            raise NotFoundError(
                "Campaign not found",
                code="campaign.not_found",
                context={"campaign_id": str(campaign_id)},
            )
        return campaign

    def find(self, campaign_id: CampaignId) -> Campaign | None:
        value = self._state.campaigns.get(campaign_id)
        return deepcopy(value) if value is not None else None

    def find_by_key(self, key: str) -> Campaign | None:
        normalized = normalize_campaign_key(key)
        for campaign in self._state.campaigns.values():
            if campaign.key == normalized:
                return deepcopy(campaign)
        return None

    def save(self, campaign: Campaign) -> None:
        existing = self.find_by_key(campaign.key)
        if existing is not None and existing.id != campaign.id:
            raise DuplicateError(
                "Campaign key already exists",
                code="campaign.key.duplicate",
                context={"key": campaign.key},
            )
        self._state.campaigns[campaign.id] = deepcopy(campaign)

    def search(
        self,
        query: CampaignQuery,
        page: OffsetPageRequest,
    ) -> Page[Campaign]:
        values = list(self._state.campaigns.values())
        if not query.include_archived:
            values = [
                item for item in values if item.status is not CampaignStatus.ARCHIVED
            ]
        if query.status is not None:
            values = [item for item in values if item.status is query.status]
        if query.owner_id is not None:
            values = [item for item in values if item.owner_id == query.owner_id]
        values.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


__all__ = ["MemoryCampaignRepository"]
