"""Application service for Campaign attribution and communication linkage."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pycrmkit.campaigns.entities import Campaign, CampaignId
from pycrmkit.campaigns.linkage import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
)
from pycrmkit.campaigns.linkage_repository import CampaignLinkageRepository
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.communication import CommunicationRecord, CommunicationRecordId
from pycrmkit.communication.repository import CommunicationRepository
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import SEGMENTABLE_ENTITY_KINDS, SegmentQueryExecutor


@dataclass(slots=True)
class CampaignLinkageService:
    """Record lightweight attribution and links to existing communications."""

    campaigns: CampaignRepository
    linkage: CampaignLinkageRepository
    communications: CommunicationRepository
    entity_resolver: SegmentQueryExecutor
    clock: Clock = field(default_factory=SystemClock)

    def add_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        *,
        source: str,
        external_ref: str | None = None,
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignAttributionReference:
        self._mutable_campaign(campaign_id)
        self._validate_target(target)
        reference = CampaignAttributionReference(
            campaign_id=campaign_id,
            target=target,
            source=source,
            recorded_at=self.clock.now(),
            external_ref=external_ref,
            actor_id=actor_id,
            metadata=dict(metadata or {}),
        )
        return self.linkage.add_attribution(reference)

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        *,
        source: str,
        external_ref: str | None = None,
    ) -> bool:
        self._mutable_campaign(campaign_id)
        self._validate_target_kind(target)
        return self.linkage.remove_attribution(
            campaign_id,
            target,
            source,
            external_ref,
        )

    def attributions(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignAttributionReference]:
        self.campaigns.get(campaign_id)
        return self.linkage.list_attributions(
            campaign_id,
            page or OffsetPageRequest(),
        )

    def link_communication(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
        *,
        role: str = "touchpoint",
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignCommunicationLink:
        self._mutable_campaign(campaign_id)
        self.communications.get_record(communication_id)
        link = CampaignCommunicationLink(
            campaign_id=campaign_id,
            communication_id=communication_id,
            linked_at=self.clock.now(),
            role=role,
            actor_id=actor_id,
            metadata=dict(metadata or {}),
        )
        return self.linkage.add_communication_link(link)

    def unlink_communication(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
    ) -> bool:
        self._mutable_campaign(campaign_id)
        return self.linkage.remove_communication_link(
            campaign_id,
            communication_id,
        )

    def communication_links(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignCommunicationLink]:
        self.campaigns.get(campaign_id)
        return self.linkage.list_communication_links(
            campaign_id,
            page or OffsetPageRequest(),
        )

    def communications_for_campaign(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CommunicationRecord]:
        request = page or OffsetPageRequest()
        links = self.communication_links(campaign_id, request)
        records = tuple(
            self.communications.get_record(link.communication_id)
            for link in links.items
        )
        return Page(
            items=records,
            limit=links.limit,
            offset=links.offset,
            total=links.total,
        )

    def _mutable_campaign(self, campaign_id: CampaignId) -> Campaign:
        campaign = self.campaigns.get(campaign_id)
        campaign.ensure_mutable()
        return campaign

    def _validate_target(self, target: EntityReference) -> None:
        self._validate_target_kind(target)
        if not self.entity_resolver.exists(target):
            raise ValidationError(
                "campaign attribution target must reference an existing CRM entity",
                code="campaign.attribution.target.not_found",
                context={
                    "entity_kind": target.kind,
                    "entity_id": str(target.id),
                },
            )

    @staticmethod
    def _validate_target_kind(target: EntityReference) -> None:
        if target.kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported campaign attribution target kind",
                code="campaign.attribution.target_kind.unsupported",
                context={"entity_kind": target.kind},
            )


__all__ = ["CampaignLinkageService"]
