"""Campaign audience persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.audience_repository import CampaignAudienceRepository


@runtime_checkable
class CampaignAudienceUnitOfWork(Protocol):
    """Optional UoW capability for Campaign audience-aware adapters."""

    @property
    def campaign_audience(self) -> CampaignAudienceRepository:
        """Campaign direct members and Segment sources in the transaction."""


__all__ = ["CampaignAudienceUnitOfWork"]
