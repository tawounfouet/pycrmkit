"""Application service for Campaign audiences and Segment sources."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.campaigns.audience_repository import CampaignAudienceRepository
from pycrmkit.campaigns.entities import Campaign, CampaignId
from pycrmkit.campaigns.repository import CampaignRepository
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import Clock, SystemClock
from pycrmkit.exceptions import ValidationError
from pycrmkit.segments import (
    SEGMENTABLE_ENTITY_KINDS,
    Segment,
    SegmentId,
    SegmentMembershipRepository,
    SegmentMode,
    SegmentQueryExecutor,
    SegmentRepository,
)


@dataclass(slots=True)
class CampaignAudienceService:
    """Manage explicit members and deterministic Segment-derived audience captures."""

    campaigns: CampaignRepository
    audience_repository: CampaignAudienceRepository
    segments: SegmentRepository
    segment_memberships: SegmentMembershipRepository
    segment_query_executor: SegmentQueryExecutor
    clock: Clock = field(default_factory=SystemClock)

    MAX_BULK_MEMBERS = 1000

    def add_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
        *,
        source: str = "manual",
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignMember:
        campaign = self._mutable_campaign(campaign_id)
        del campaign
        self._validate_member(entity)
        member = CampaignMember(
            campaign_id=campaign_id,
            entity=entity,
            added_at=self.clock.now(),
            source=source,
            actor_id=actor_id,
            metadata=dict(metadata or {}),
        )
        return self.audience_repository.add_member(member)

    def add_members(
        self,
        campaign_id: CampaignId,
        entities: Iterable[EntityReference],
        *,
        source: str = "manual",
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CampaignMember, ...]:
        self._mutable_campaign(campaign_id)
        references = tuple(entities)
        self._validate_bulk(references)
        for entity in references:
            self._validate_member(entity)
        now = self.clock.now()
        members = tuple(
            CampaignMember(
                campaign_id=campaign_id,
                entity=entity,
                added_at=now,
                source=source,
                actor_id=actor_id,
                metadata=dict(metadata or {}),
            )
            for entity in references
        )
        return self.audience_repository.add_members(members)

    def remove_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        self._mutable_campaign(campaign_id)
        self._validate_kind(entity)
        return self.audience_repository.remove_member(campaign_id, entity)

    def remove_members(
        self,
        campaign_id: CampaignId,
        entities: Iterable[EntityReference],
    ) -> int:
        self._mutable_campaign(campaign_id)
        references = tuple(dict.fromkeys(entities))
        self._validate_bulk(references)
        for entity in references:
            self._validate_kind(entity)
        return self.audience_repository.remove_members(campaign_id, references)

    def members(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignMember]:
        self.campaigns.get(campaign_id)
        return self.audience_repository.list_members(
            campaign_id,
            page or OffsetPageRequest(),
        )

    def audience(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        self.campaigns.get(campaign_id)
        return self.audience_repository.audience(
            campaign_id,
            page or OffsetPageRequest(),
        )

    def audience_count(self, campaign_id: CampaignId) -> int:
        self.campaigns.get(campaign_id)
        return self.audience_repository.audience_count(campaign_id)

    def contains(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        self.campaigns.get(campaign_id)
        self._validate_kind(entity)
        return self.audience_repository.contains(campaign_id, entity)

    def attach_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
        *,
        actor_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignSegmentSource:
        self._mutable_campaign(campaign_id)
        segment = self.segments.get(segment_id)
        segment.ensure_active()
        captured = self._capture_segment(segment)
        now = self.clock.now()
        source = CampaignSegmentSource(
            campaign_id=campaign_id,
            segment_id=segment.id,
            segment_revision=segment.revision,
            entity_kind=segment.entity_kind,
            attached_at=now,
            captured_at=now,
            member_count=len(captured),
            actor_id=actor_id,
            metadata=dict(metadata or {}),
        )
        return self.audience_repository.add_segment_source(source, captured)

    def refresh_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
        *,
        actor_id: str | None = None,
    ) -> CampaignSegmentSource:
        self._mutable_campaign(campaign_id)
        previous = self.audience_repository.get_segment_source(
            campaign_id,
            segment_id,
        )
        segment = self.segments.get(segment_id)
        segment.ensure_active()
        captured = self._capture_segment(segment)
        refreshed = CampaignSegmentSource(
            campaign_id=campaign_id,
            segment_id=segment.id,
            segment_revision=segment.revision,
            entity_kind=segment.entity_kind,
            attached_at=previous.attached_at,
            captured_at=self.clock.now(),
            member_count=len(captured),
            actor_id=actor_id,
            metadata=previous.metadata,
        )
        return self.audience_repository.replace_segment_source(
            refreshed,
            captured,
        )

    def detach_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> bool:
        self._mutable_campaign(campaign_id)
        return self.audience_repository.remove_segment_source(
            campaign_id,
            segment_id,
        )

    def segment_sources(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignSegmentSource]:
        self.campaigns.get(campaign_id)
        return self.audience_repository.list_segment_sources(
            campaign_id,
            page or OffsetPageRequest(),
        )

    def _capture_segment(self, segment: Segment) -> tuple[EntityReference, ...]:
        captured: list[EntityReference] = []
        offset = 0
        captured_at = self.clock.now()
        while True:
            request = OffsetPageRequest(
                limit=OffsetPageRequest.MAX_LIMIT,
                offset=offset,
            )
            if segment.mode is SegmentMode.DYNAMIC:
                assert segment.query is not None
                page = self.segment_query_executor.execute(
                    segment.entity_kind,
                    segment.query,
                    request,
                    at=captured_at,
                )
                references = page.items
            else:
                stored = self.segment_memberships.list(segment.id, request)
                references = tuple(member.entity for member in stored.items)
                page = Page(
                    items=references,
                    limit=stored.limit,
                    offset=stored.offset,
                    total=stored.total,
                )
            captured.extend(references)
            if not page.has_next:
                break
            offset += len(page.items)
        return tuple(dict.fromkeys(captured))

    def _mutable_campaign(self, campaign_id: CampaignId) -> Campaign:
        campaign = self.campaigns.get(campaign_id)
        campaign.ensure_mutable()
        return campaign

    def _validate_member(self, entity: EntityReference) -> None:
        self._validate_kind(entity)
        if not self.segment_query_executor.exists(entity):
            raise ValidationError(
                "campaign member must reference an existing CRM entity",
                code="campaign.member.not_found",
                context={
                    "entity_kind": entity.kind,
                    "entity_id": str(entity.id),
                },
            )

    @staticmethod
    def _validate_kind(entity: EntityReference) -> None:
        if entity.kind not in SEGMENTABLE_ENTITY_KINDS:
            raise ValidationError(
                "unsupported campaign member entity kind",
                code="campaign.member.kind.unsupported",
                context={"entity_kind": entity.kind},
            )

    def _validate_bulk(self, entities: tuple[EntityReference, ...]) -> None:
        if len(entities) > self.MAX_BULK_MEMBERS:
            raise ValidationError(
                "campaign membership batch exceeds the configured limit",
                code="campaign.member.bulk_limit",
                context={"max_members": self.MAX_BULK_MEMBERS},
            )
        if len(entities) != len(set(entities)):
            raise ValidationError(
                "campaign membership batch contains duplicate references",
                code="campaign.member.batch_duplicate",
            )


__all__ = ["CampaignAudienceService"]
