"""Persistence contracts for Campaign attribution and communication linkage."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.entities import CampaignId
from pycrmkit.campaigns.linkage import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference


@runtime_checkable
class CampaignLinkageRepository(Protocol):
    """Backend-neutral Campaign attribution and communication linkage."""

    def add_attribution(
        self,
        reference: CampaignAttributionReference,
    ) -> CampaignAttributionReference:
        ...

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ) -> bool:
        ...

    def list_attributions(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignAttributionReference]:
        ...

    def add_communication_link(
        self,
        link: CampaignCommunicationLink,
    ) -> CampaignCommunicationLink:
        ...

    def remove_communication_link(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
    ) -> bool:
        ...

    def list_communication_links(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignCommunicationLink]:
        ...


__all__ = ["CampaignLinkageRepository"]
