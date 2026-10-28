"""Django repository for direct and materialized Campaign audience membership."""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from pycrmkit.campaigns import CampaignId, CampaignMember, CampaignSegmentSource
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.integrations.django.campaign_codec import (
    campaign_member_from_model,
    campaign_member_to_model,
    campaign_segment_member_to_model,
    campaign_segment_source_from_model,
    campaign_segment_source_to_model,
    entity_reference,
)
from pycrmkit.integrations.django.campaign_repositories import _page
from pycrmkit.integrations.django.models import (
    CampaignMemberModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)
from pycrmkit.segments import SegmentId


class DjangoCampaignAudienceRepository:
    """Django ORM implementation of the Campaign audience Protocol."""

    def add_member(self, member: CampaignMember) -> CampaignMember:
        if self._direct_exists(member.campaign_id, member.entity):
            raise self._member_duplicate(member)
        try:
            with transaction.atomic():
                campaign_member_to_model(member).save(force_insert=True)
        except IntegrityError as error:
            raise self._member_duplicate(member) from error
        return member

    def add_members(
        self, members: tuple[CampaignMember, ...]
    ) -> tuple[CampaignMember, ...]:
        keys = [
            (str(m.campaign_id), m.entity.kind, str(m.entity.id))
            for m in members
        ]
        if len(keys) != len(set(keys)):
            raise DuplicateError(
                "Campaign membership batch contains duplicates",
                code="campaign.member.batch_duplicate",
            )
        for member in members:
            if self._direct_exists(member.campaign_id, member.entity):
                raise self._member_duplicate(member)
        try:
            with transaction.atomic():
                CampaignMemberModel.objects.bulk_create(
                    [campaign_member_to_model(m) for m in members]
                )
        except IntegrityError as error:
            raise DuplicateError(
                "Campaign membership already exists",
                code="campaign.member.duplicate",
            ) from error
        return members

    def remove_member(
        self, campaign_id: CampaignId, entity: EntityReference
    ) -> bool:
        deleted, _ = CampaignMemberModel.objects.filter(
            campaign_id=str(campaign_id),
            entity_kind=entity.kind,
            entity_id=str(entity.id),
        ).delete()
        return int(deleted) > 0

    def remove_members(
        self, campaign_id: CampaignId, entities: tuple[EntityReference, ...]
    ) -> int:
        unique = tuple(dict.fromkeys(entities))
        if not unique:
            return 0
        targets = Q()
        for entity in unique:
            targets |= Q(entity_kind=entity.kind, entity_id=str(entity.id))
        deleted, _ = CampaignMemberModel.objects.filter(
            Q(campaign_id=str(campaign_id)) & targets
        ).delete()
        return deleted

    def list_members(
        self, campaign_id: CampaignId, page: OffsetPageRequest
    ) -> Page[CampaignMember]:
        queryset = CampaignMemberModel.objects.filter(
            campaign_id=str(campaign_id)
        ).order_by("added_at", "entity_kind", "entity_id", "id")
        return _page(queryset, page, campaign_member_from_model)

    def add_segment_source(
        self, source: CampaignSegmentSource, members: tuple[EntityReference, ...]
    ) -> CampaignSegmentSource:
        if self._source_queryset(source.campaign_id, source.segment_id).exists():
            raise self._source_duplicate(source)
        self._validate_capture(source, members)
        try:
            with transaction.atomic():
                row = campaign_segment_source_to_model(source)
                row.save(force_insert=True)
                CampaignSegmentMemberModel.objects.bulk_create(
                    [campaign_segment_member_to_model(row.id, m) for m in members]
                )
        except IntegrityError as error:
            if self._source_queryset(source.campaign_id, source.segment_id).exists():
                raise self._source_duplicate(source) from error
            raise
        return source

    def replace_segment_source(
        self, source: CampaignSegmentSource, members: tuple[EntityReference, ...]
    ) -> CampaignSegmentSource:
        self._validate_capture(source, members)
        with transaction.atomic():
            row = self._source_queryset(
                source.campaign_id, source.segment_id
            ).select_for_update().first()
            if row is None:
                raise self._source_missing(source.campaign_id, source.segment_id)
            campaign_segment_source_to_model(source, row)
            row.save()
            CampaignSegmentMemberModel.objects.filter(source_id=row.pk).delete()
            CampaignSegmentMemberModel.objects.bulk_create(
                [campaign_segment_member_to_model(row.id, m) for m in members]
            )
        return source

    def get_segment_source(
        self, campaign_id: CampaignId, segment_id: SegmentId
    ) -> CampaignSegmentSource:
        row = self._source_queryset(campaign_id, segment_id).first()
        if row is None:
            raise self._source_missing(campaign_id, segment_id)
        return campaign_segment_source_from_model(row)

    def remove_segment_source(
        self, campaign_id: CampaignId, segment_id: SegmentId
    ) -> bool:
        deleted, _ = self._source_queryset(campaign_id, segment_id).delete()
        return deleted > 0

    def list_segment_sources(
        self, campaign_id: CampaignId, page: OffsetPageRequest
    ) -> Page[CampaignSegmentSource]:
        queryset = CampaignSegmentSourceModel.objects.filter(
            campaign_id=str(campaign_id)
        ).order_by("attached_at", "segment_id", "id")
        return _page(queryset, page, campaign_segment_source_from_model)

    def audience(
        self, campaign_id: CampaignId, page: OffsetPageRequest
    ) -> Page[EntityReference]:
        rows = self._audience_relation(campaign_id)
        total = rows.count()
        page_rows = rows[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(
                entity_reference(kind, identifier)
                for kind, identifier in page_rows
            ),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def audience_count(self, campaign_id: CampaignId) -> int:
        return int(self._audience_relation(campaign_id).count())

    def contains(
        self, campaign_id: CampaignId, entity: EntityReference
    ) -> bool:
        if self._direct_exists(campaign_id, entity):
            return True
        return CampaignSegmentMemberModel.objects.filter(
            source__campaign_id=str(campaign_id),
            entity_kind=entity.kind,
            entity_id=str(entity.id),
        ).exists()

    @staticmethod
    def _audience_relation(campaign_id: CampaignId) -> QuerySet[Any]:
        direct = CampaignMemberModel.objects.filter(
            campaign_id=str(campaign_id)
        ).order_by().values_list("entity_kind", "entity_id")
        captured = CampaignSegmentMemberModel.objects.filter(
            source__campaign_id=str(campaign_id)
        ).order_by().values_list("entity_kind", "entity_id")
        return direct.union(captured).order_by("entity_kind", "entity_id")

    @staticmethod
    def _source_queryset(
        campaign_id: CampaignId, segment_id: SegmentId
    ) -> QuerySet[CampaignSegmentSourceModel]:
        return CampaignSegmentSourceModel.objects.filter(
            campaign_id=str(campaign_id), segment_id=str(segment_id)
        )

    @staticmethod
    def _direct_exists(campaign_id: CampaignId, entity: EntityReference) -> bool:
        return CampaignMemberModel.objects.filter(
            campaign_id=str(campaign_id),
            entity_kind=entity.kind,
            entity_id=str(entity.id),
        ).exists()

    @staticmethod
    def _member_duplicate(member: CampaignMember) -> DuplicateError:
        return DuplicateError(
            "Campaign membership already exists",
            code="campaign.member.duplicate",
            context={
                "campaign_id": str(member.campaign_id),
                "entity_kind": member.entity.kind,
                "entity_id": str(member.entity.id),
            },
        )

    @staticmethod
    def _source_duplicate(source: CampaignSegmentSource) -> DuplicateError:
        return DuplicateError(
            "Campaign Segment source already exists",
            code="campaign.segment_source.duplicate",
            context={
                "campaign_id": str(source.campaign_id),
                "segment_id": str(source.segment_id),
            },
        )

    @staticmethod
    def _source_missing(campaign_id: CampaignId, segment_id: SegmentId) -> NotFoundError:
        return NotFoundError(
            "Campaign Segment source not found",
            code="campaign.segment_source.not_found",
            context={
                "campaign_id": str(campaign_id),
                "segment_id": str(segment_id),
            },
        )

    @staticmethod
    def _validate_capture(
        source: CampaignSegmentSource, members: tuple[EntityReference, ...]
    ) -> None:
        if len(set(members)) != len(members):
            raise DuplicateError(
                "Campaign Segment capture contains duplicate members",
                code="campaign.segment_source.members.duplicate",
            )
        if source.member_count != len(members):
            raise ValueError("Campaign Segment source member_count does not match capture")
        if any(m.kind != source.entity_kind for m in members):
            raise ValueError(
                "Campaign Segment capture contains an incompatible entity kind"
            )


__all__ = ["DjangoCampaignAudienceRepository"]
