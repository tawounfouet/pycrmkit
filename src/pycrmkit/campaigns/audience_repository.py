"""Persistence contract for Campaign audiences."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.campaigns.entities import CampaignId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.segments import SegmentId


@runtime_checkable
class CampaignAudienceRepository(Protocol):
    """Backend-neutral direct membership and materialized Segment-source contract."""

    def add_member(self, member: CampaignMember) -> CampaignMember:
        """Persist one explicit Campaign member."""

    def add_members(
        self,
        members: tuple[CampaignMember, ...],
    ) -> tuple[CampaignMember, ...]:
        """Persist one explicit membership batch atomically."""

    def remove_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        """Remove one explicit member idempotently."""

    def remove_members(
        self,
        campaign_id: CampaignId,
        entities: tuple[EntityReference, ...],
    ) -> int:
        """Remove explicit members and return the number removed."""

    def list_members(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignMember]:
        """List explicit Campaign members only."""

    def add_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        """Attach one Segment and its materialized population."""

    def replace_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        """Replace one attached Segment capture atomically."""

    def get_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> CampaignSegmentSource:
        """Return one attached Segment source or raise NotFoundError."""

    def remove_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> bool:
        """Detach one Segment source and its materialized population."""

    def list_segment_sources(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignSegmentSource]:
        """List attached Segment sources."""

    def audience(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[EntityReference]:
        """Return the de-duplicated union of direct and Segment-derived members."""

    def audience_count(self, campaign_id: CampaignId) -> int:
        """Return exact de-duplicated audience size."""

    def contains(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        """Return whether the final Campaign audience contains one entity."""


__all__ = ["CampaignAudienceRepository"]
