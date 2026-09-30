"""In-memory Campaign audience repository."""

from __future__ import annotations

from copy import deepcopy

from pycrmkit.campaigns import CampaignId
from pycrmkit.campaigns.audience import CampaignMember, CampaignSegmentSource
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.memory._state import _MemoryState


class MemoryCampaignAudienceRepository:
    """Copy-isolated direct membership and materialized Segment-source storage."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def add_member(self, member: CampaignMember) -> CampaignMember:
        key = (member.campaign_id, member.entity)
        if key in self._state.campaign_members:
            raise DuplicateError(
                "Campaign membership already exists",
                code="campaign.member.duplicate",
                context={
                    "campaign_id": str(member.campaign_id),
                    "entity_kind": member.entity.kind,
                    "entity_id": str(member.entity.id),
                },
            )
        self._state.campaign_members[key] = deepcopy(member)
        return deepcopy(member)

    def add_members(
        self,
        members: tuple[CampaignMember, ...],
    ) -> tuple[CampaignMember, ...]:
        keys = [(member.campaign_id, member.entity) for member in members]
        if len(keys) != len(set(keys)):
            raise DuplicateError(
                "Campaign membership batch contains duplicates",
                code="campaign.member.batch_duplicate",
            )
        for member, key in zip(members, keys, strict=True):
            if key in self._state.campaign_members:
                raise DuplicateError(
                    "Campaign membership already exists",
                    code="campaign.member.duplicate",
                    context={
                        "campaign_id": str(member.campaign_id),
                        "entity_kind": member.entity.kind,
                        "entity_id": str(member.entity.id),
                    },
                )
        for member, key in zip(members, keys, strict=True):
            self._state.campaign_members[key] = deepcopy(member)
        return tuple(deepcopy(members))

    def remove_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        return self._state.campaign_members.pop((campaign_id, entity), None) is not None

    def remove_members(
        self,
        campaign_id: CampaignId,
        entities: tuple[EntityReference, ...],
    ) -> int:
        return sum(
            self._state.campaign_members.pop((campaign_id, entity), None) is not None
            for entity in dict.fromkeys(entities)
        )

    def list_members(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignMember]:
        values = [
            member
            for (stored_campaign_id, _), member in self._state.campaign_members.items()
            if stored_campaign_id == campaign_id
        ]
        values.sort(
            key=lambda item: (item.added_at, item.entity.kind, str(item.entity.id))
        )
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def add_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        key = (source.campaign_id, source.segment_id)
        if key in self._state.campaign_segment_sources:
            raise DuplicateError(
                "Campaign Segment source already exists",
                code="campaign.segment_source.duplicate",
                context={
                    "campaign_id": str(source.campaign_id),
                    "segment_id": str(source.segment_id),
                },
            )
        self._validate_capture(source, members)
        self._state.campaign_segment_sources[key] = deepcopy(source)
        self._state.campaign_segment_members[key] = tuple(deepcopy(members))
        return deepcopy(source)

    def replace_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        key = (source.campaign_id, source.segment_id)
        if key not in self._state.campaign_segment_sources:
            raise NotFoundError(
                "Campaign Segment source not found",
                code="campaign.segment_source.not_found",
                context={
                    "campaign_id": str(source.campaign_id),
                    "segment_id": str(source.segment_id),
                },
            )
        self._validate_capture(source, members)
        self._state.campaign_segment_sources[key] = deepcopy(source)
        self._state.campaign_segment_members[key] = tuple(deepcopy(members))
        return deepcopy(source)

    def get_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> CampaignSegmentSource:
        value = self._state.campaign_segment_sources.get((campaign_id, segment_id))
        if value is None:
            raise NotFoundError(
                "Campaign Segment source not found",
                code="campaign.segment_source.not_found",
                context={
                    "campaign_id": str(campaign_id),
                    "segment_id": str(segment_id),
                },
            )
        return deepcopy(value)

    def remove_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> bool:
        key = (campaign_id, segment_id)
        removed = self._state.campaign_segment_sources.pop(key, None)
        self._state.campaign_segment_members.pop(key, None)
        return removed is not None

    def list_segment_sources(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignSegmentSource]:
        values = [
            source
            for (stored_campaign_id, _), source
            in self._state.campaign_segment_sources.items()
            if stored_campaign_id == campaign_id
        ]
        values.sort(key=lambda item: (item.attached_at, str(item.segment_id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def audience(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[EntityReference]:
        values = self._audience_values(campaign_id)
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def audience_count(self, campaign_id: CampaignId) -> int:
        return len(self._audience_values(campaign_id))

    def contains(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        if (campaign_id, entity) in self._state.campaign_members:
            return True
        return any(
            entity in members
            for (stored_campaign_id, _), members
            in self._state.campaign_segment_members.items()
            if stored_campaign_id == campaign_id
        )

    def _audience_values(
        self,
        campaign_id: CampaignId,
    ) -> tuple[EntityReference, ...]:
        values = {
            entity
            for stored_campaign_id, entity in self._state.campaign_members
            if stored_campaign_id == campaign_id
        }
        for (stored_campaign_id, _), members in self._state.campaign_segment_members.items():
            if stored_campaign_id == campaign_id:
                values.update(members)
        return tuple(sorted(values, key=lambda item: (item.kind, str(item.id))))

    @staticmethod
    def _validate_capture(
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> None:
        unique = tuple(dict.fromkeys(members))
        if len(unique) != len(members):
            raise DuplicateError(
                "Campaign Segment capture contains duplicate members",
                code="campaign.segment_source.members.duplicate",
            )
        if source.member_count != len(members):
            raise ValueError("Campaign Segment source member_count does not match capture")
        if any(member.kind != source.entity_kind for member in members):
            raise ValueError("Campaign Segment capture contains an incompatible entity kind")


__all__ = ["MemoryCampaignAudienceRepository"]
