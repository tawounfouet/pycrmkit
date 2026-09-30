"""Campaign linkage persistence capability protocol."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.linkage_repository import CampaignLinkageRepository
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.communication.repository import CommunicationRepository
from pycrmkit.segments import SegmentQueryExecutor


@runtime_checkable
class CampaignLinkageUnitOfWork(Protocol):
    """Capabilities required for Campaign attribution and communication linkage."""

    @property
    def campaigns(self) -> CampaignRepository:
        ...

    @property
    def campaign_linkage(self) -> CampaignLinkageRepository:
        ...

    @property
    def communications(self) -> CommunicationRepository:
        ...

    @property
    def segment_query_executor(self) -> SegmentQueryExecutor:
        ...


__all__ = ["CampaignLinkageUnitOfWork"]
