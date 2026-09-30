"""Campaign linkage persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.linkage_repository import CampaignLinkageRepository


@runtime_checkable
class CampaignLinkageUnitOfWork(Protocol):
    """Optional UoW capability for Campaign attribution/communication linkage."""

    @property
    def campaign_linkage(self) -> CampaignLinkageRepository:
        ...


__all__ = ["CampaignLinkageUnitOfWork"]
