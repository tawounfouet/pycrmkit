"""SQLAlchemy CampaignAudienceRepository implementation."""

from __future__ import annotations

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.selectable import Subquery

from pycrmkit.campaigns import (
    CampaignId,
    CampaignMember,
    CampaignSegmentSource,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.segments import SegmentId
from pycrmkit.storage.sqlalchemy.campaign_codec import (
    campaign_member_from_model,
    campaign_member_to_model,
    campaign_segment_member_to_model,
    campaign_segment_source_from_model,
    campaign_segment_source_to_model,
)
from pycrmkit.storage.sqlalchemy.mappers import entity_reference
from pycrmkit.storage.sqlalchemy.models.campaign import (
    CampaignMemberModel,
    CampaignSegmentMemberModel,
    CampaignSegmentSourceModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyCampaignAudienceRepository:
    """Session-scoped Campaign audience and materialized Segment-source storage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_member(self, member: CampaignMember) -> CampaignMember:
        if self._direct_member_exists(member.campaign_id, member.entity):
            raise DuplicateError(
                "Campaign membership already exists",
                code="campaign.member.duplicate",
                context={
                    "campaign_id": str(member.campaign_id),
                    "entity_kind": member.entity.kind,
                    "entity_id": str(member.entity.id),
                },
            )
        self.session.add(campaign_member_to_model(member))
        return member

    def add_members(
        self,
        members: tuple[CampaignMember, ...],
    ) -> tuple[CampaignMember, ...]:
        keys = [
            (str(member.campaign_id), member.entity.kind, str(member.entity.id))
            for member in members
        ]
        if len(keys) != len(set(keys)):
            raise DuplicateError(
                "Campaign membership batch contains duplicates",
                code="campaign.member.batch_duplicate",
            )

        for member in members:
            if self._direct_member_exists(member.campaign_id, member.entity):
                raise DuplicateError(
                    "Campaign membership already exists",
                    code="campaign.member.duplicate",
                    context={
                        "campaign_id": str(member.campaign_id),
                        "entity_kind": member.entity.kind,
                        "entity_id": str(member.entity.id),
                    },
                )

        self.session.add_all(
            [campaign_member_to_model(member) for member in members]
        )
        return members

    def remove_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        if not self._direct_member_exists(campaign_id, entity):
            return False
        self.session.execute(
            delete(CampaignMemberModel).where(
                CampaignMemberModel.campaign_id == str(campaign_id),
                CampaignMemberModel.entity_kind == entity.kind,
                CampaignMemberModel.entity_id == str(entity.id),
            )
        )
        return True

    def remove_members(
        self,
        campaign_id: CampaignId,
        entities: tuple[EntityReference, ...],
    ) -> int:
        unique = tuple(dict.fromkeys(entities))
        removed = 0
        for entity in unique:
            if self.remove_member(campaign_id, entity):
                removed += 1
        return removed

    def list_members(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignMember]:
        statement = (
            select(CampaignMemberModel)
            .where(CampaignMemberModel.campaign_id == str(campaign_id))
            .order_by(
                CampaignMemberModel.added_at.asc(),
                CampaignMemberModel.entity_kind.asc(),
                CampaignMemberModel.entity_id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            campaign_member_from_model,
        )

    def add_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        key = (str(source.campaign_id), str(source.segment_id))
        if self.session.get(CampaignSegmentSourceModel, key) is not None:
            raise DuplicateError(
                "Campaign Segment source already exists",
                code="campaign.segment_source.duplicate",
                context={
                    "campaign_id": str(source.campaign_id),
                    "segment_id": str(source.segment_id),
                },
            )

        self._validate_capture(source, members)
        self.session.add(campaign_segment_source_to_model(source))
        self.session.add_all(
            [
                campaign_segment_member_to_model(
                    source.campaign_id,
                    source.segment_id,
                    member,
                )
                for member in members
            ]
        )
        return source

    def replace_segment_source(
        self,
        source: CampaignSegmentSource,
        members: tuple[EntityReference, ...],
    ) -> CampaignSegmentSource:
        key = (str(source.campaign_id), str(source.segment_id))
        current = self.session.get(CampaignSegmentSourceModel, key)
        if current is None:
            raise self._segment_source_not_found(
                source.campaign_id,
                source.segment_id,
            )

        self._validate_capture(source, members)
        campaign_segment_source_to_model(source, current)
        self.session.execute(
            delete(CampaignSegmentMemberModel).where(
                CampaignSegmentMemberModel.campaign_id
                == str(source.campaign_id),
                CampaignSegmentMemberModel.segment_id
                == str(source.segment_id),
            )
        )
        self.session.add_all(
            [
                campaign_segment_member_to_model(
                    source.campaign_id,
                    source.segment_id,
                    member,
                )
                for member in members
            ]
        )
        return source

    def get_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> CampaignSegmentSource:
        model = self.session.get(
            CampaignSegmentSourceModel,
            (str(campaign_id), str(segment_id)),
        )
        if model is None:
            raise self._segment_source_not_found(campaign_id, segment_id)
        return campaign_segment_source_from_model(model)

    def remove_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> bool:
        key = (str(campaign_id), str(segment_id))
        if self.session.get(CampaignSegmentSourceModel, key) is None:
            return False

        # Explicit child deletion keeps SQLite contract tests equivalent even when
        # FK cascade enforcement is not enabled; PostgreSQL still owns the CASCADE.
        self.session.execute(
            delete(CampaignSegmentMemberModel).where(
                CampaignSegmentMemberModel.campaign_id == str(campaign_id),
                CampaignSegmentMemberModel.segment_id == str(segment_id),
            )
        )
        self.session.execute(
            delete(CampaignSegmentSourceModel).where(
                CampaignSegmentSourceModel.campaign_id == str(campaign_id),
                CampaignSegmentSourceModel.segment_id == str(segment_id),
            )
        )
        return True

    def list_segment_sources(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignSegmentSource]:
        statement = (
            select(CampaignSegmentSourceModel)
            .where(
                CampaignSegmentSourceModel.campaign_id == str(campaign_id)
            )
            .order_by(
                CampaignSegmentSourceModel.attached_at.asc(),
                CampaignSegmentSourceModel.segment_id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            campaign_segment_source_from_model,
        )

    def audience(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[EntityReference]:
        relation = self._audience_relation(campaign_id)
        total = int(
            self.session.scalar(
                select(func.count()).select_from(relation)
            )
            or 0
        )
        rows = self.session.execute(
            select(
                relation.c.entity_kind,
                relation.c.entity_id,
            )
            .order_by(
                relation.c.entity_kind.asc(),
                relation.c.entity_id.asc(),
            )
            .offset(page.offset)
            .limit(page.limit)
        ).all()
        return Page(
            items=tuple(
                entity_reference(row.entity_kind, row.entity_id)
                for row in rows
            ),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def audience_count(self, campaign_id: CampaignId) -> int:
        relation = self._audience_relation(campaign_id)
        return int(
            self.session.scalar(
                select(func.count()).select_from(relation)
            )
            or 0
        )

    def contains(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        direct = exists(
            select(CampaignMemberModel.id).where(
                CampaignMemberModel.campaign_id == str(campaign_id),
                CampaignMemberModel.entity_kind == entity.kind,
                CampaignMemberModel.entity_id == str(entity.id),
            )
        )
        captured = exists(
            select(CampaignSegmentMemberModel.id).where(
                CampaignSegmentMemberModel.campaign_id == str(campaign_id),
                CampaignSegmentMemberModel.entity_kind == entity.kind,
                CampaignSegmentMemberModel.entity_id == str(entity.id),
            )
        )
        return bool(self.session.scalar(select(or_(direct, captured))))

    def _direct_member_exists(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        return (
            self.session.scalar(
                select(CampaignMemberModel.id).where(
                    CampaignMemberModel.campaign_id == str(campaign_id),
                    CampaignMemberModel.entity_kind == entity.kind,
                    CampaignMemberModel.entity_id == str(entity.id),
                )
            )
            is not None
        )

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
            raise ValueError(
                "Campaign Segment source member_count does not match capture"
            )
        if any(member.kind != source.entity_kind for member in members):
            raise ValueError(
                "Campaign Segment capture contains an incompatible entity kind"
            )

    @staticmethod
    def _segment_source_not_found(
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> NotFoundError:
        return NotFoundError(
            "Campaign Segment source not found",
            code="campaign.segment_source.not_found",
            context={
                "campaign_id": str(campaign_id),
                "segment_id": str(segment_id),
            },
        )

    @staticmethod
    def _audience_relation(campaign_id: CampaignId) -> Subquery:
        direct = select(
            CampaignMemberModel.entity_kind.label("entity_kind"),
            CampaignMemberModel.entity_id.label("entity_id"),
        ).where(CampaignMemberModel.campaign_id == str(campaign_id))
        captured = select(
            CampaignSegmentMemberModel.entity_kind.label("entity_kind"),
            CampaignSegmentMemberModel.entity_id.label("entity_id"),
        ).where(
            CampaignSegmentMemberModel.campaign_id == str(campaign_id)
        )
        return direct.union(captured).subquery()


__all__ = ["SQLAlchemyCampaignAudienceRepository"]
