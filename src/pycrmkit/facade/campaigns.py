"""Campaigns facade namespace."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime

from pycrmkit.campaigns import (
    Campaign,
    CampaignAttributionReference,
    CampaignAudienceService,
    CampaignAudienceUnitOfWork,
    CampaignCommunicationLink,
    CampaignId,
    CampaignLinkageService,
    CampaignLinkageUnitOfWork,
    CampaignMember,
    CampaignQuery,
    CampaignSegmentSource,
    CampaignService,
    CampaignUnitOfWork,
    CampaignUpdate,
    UnsetType,
)
from pycrmkit.communication import CommunicationRecord, CommunicationRecordId
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import IntegrationError
from pycrmkit.facade._runtime import CRMRuntime
from pycrmkit.segments import SegmentId, SegmentUnitOfWork


class CampaignsAPI:
    """Transactional facade for CRM Campaign metadata."""

    def __init__(self, runtime: CRMRuntime) -> None:
        self._runtime = runtime

    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        starts_at: datetime | None = None,
        ends_at: datetime | None = None,
        owner_id: EntityId | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> Campaign:
        with self._runtime.uow_factory() as uow:
            campaign = self._service(self._capabilities(uow)).create(
                key=key,
                name=name,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                owner_id=owner_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.created",
                aggregate_type="campaign",
                aggregate_id=campaign.id,
                changes={
                    "fields": [
                        "key",
                        "name",
                        "description",
                        "starts_at",
                        "ends_at",
                        "owner_id",
                        "metadata",
                    ]
                },
                payload={
                    "key": campaign.key,
                    "status": campaign.status.value,
                    "revision": campaign.revision,
                },
            )
            uow.commit()
            return campaign

    def get(self, campaign_id: CampaignId) -> Campaign:
        with self._runtime.uow_factory() as uow:
            return self._capabilities(uow).campaigns.get(campaign_id)

    def list(
        self,
        query: CampaignQuery | None = None,
        page: OffsetPageRequest | None = None,
    ) -> Page[Campaign]:
        with self._runtime.uow_factory() as uow:
            return self._service(self._capabilities(uow)).list(query, page)

    def update(
        self,
        campaign_id: CampaignId,
        changes: CampaignUpdate,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        with self._runtime.uow_factory() as uow:
            before = self._capabilities(uow).campaigns.get(campaign_id)
            campaign = self._service(self._capabilities(uow)).update(
                campaign_id,
                changes,
                expected_revision=expected_revision,
            )
            if campaign.revision != before.revision:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.updated",
                    aggregate_type="campaign",
                    aggregate_id=campaign.id,
                    changes={"fields": self._changed_fields(changes)},
                    payload={"revision": campaign.revision},
                )
            uow.commit()
            return campaign

    def activate(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        return self._transition(
            campaign_id,
            transition="activate",
            event_type="campaign.activated",
            expected_revision=expected_revision,
        )

    def complete(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        return self._transition(
            campaign_id,
            transition="complete",
            event_type="campaign.completed",
            expected_revision=expected_revision,
        )

    def archive(
        self,
        campaign_id: CampaignId,
        *,
        expected_revision: int | None = None,
    ) -> Campaign:
        return self._transition(
            campaign_id,
            transition="archive",
            event_type="campaign.archived",
            expected_revision=expected_revision,
        )

    def add_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
        *,
        source: str = "manual",
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignMember:
        with self._runtime.uow_factory() as uow:
            member = self._audience_service(uow).add_member(
                campaign_id,
                entity,
                source=source,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.member_added",
                aggregate_type="campaign",
                aggregate_id=campaign_id,
                changes={"fields": ["members"]},
                payload={
                    "entity_kind": entity.kind,
                    "entity_id": str(entity.id),
                    "source": member.source,
                },
            )
            uow.commit()
            return member

    def add_members(
        self,
        campaign_id: CampaignId,
        entities: Iterable[EntityReference],
        *,
        source: str = "manual",
        metadata: Mapping[str, object] | None = None,
    ) -> tuple[CampaignMember, ...]:
        with self._runtime.uow_factory() as uow:
            members = self._audience_service(uow).add_members(
                campaign_id,
                entities,
                source=source,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            if members:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.members_added",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["members"]},
                    payload={
                        "member_count": len(members),
                        "source": source,
                    },
                )
            uow.commit()
            return members

    def remove_member(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = self._audience_service(uow).remove_member(campaign_id, entity)
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.member_removed",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["members"]},
                    payload={
                        "entity_kind": entity.kind,
                        "entity_id": str(entity.id),
                    },
                )
            uow.commit()
            return removed

    def remove_members(
        self,
        campaign_id: CampaignId,
        entities: Iterable[EntityReference],
    ) -> int:
        with self._runtime.uow_factory() as uow:
            removed = self._audience_service(uow).remove_members(
                campaign_id,
                entities,
            )
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.members_removed",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["members"]},
                    payload={"member_count": removed},
                )
            uow.commit()
            return removed

    def members(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignMember]:
        with self._runtime.uow_factory() as uow:
            return self._audience_service(uow).members(campaign_id, page)

    def audience(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[EntityReference]:
        with self._runtime.uow_factory() as uow:
            return self._audience_service(uow).audience(campaign_id, page)

    def audience_count(self, campaign_id: CampaignId) -> int:
        with self._runtime.uow_factory() as uow:
            return self._audience_service(uow).audience_count(campaign_id)

    def contains(
        self,
        campaign_id: CampaignId,
        entity: EntityReference,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            return self._audience_service(uow).contains(campaign_id, entity)

    def attach_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignSegmentSource:
        with self._runtime.uow_factory() as uow:
            source = self._audience_service(uow).attach_segment_source(
                campaign_id,
                segment_id,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.segment_source_attached",
                aggregate_type="campaign",
                aggregate_id=campaign_id,
                changes={"fields": ["segment_sources", "audience"]},
                payload={
                    "segment_id": str(segment_id),
                    "segment_revision": source.segment_revision,
                    "member_count": source.member_count,
                    "entity_kind": source.entity_kind,
                },
            )
            uow.commit()
            return source

    def refresh_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> CampaignSegmentSource:
        with self._runtime.uow_factory() as uow:
            source = self._audience_service(uow).refresh_segment_source(
                campaign_id,
                segment_id,
                actor_id=self._runtime.context.actor_id,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.segment_source_refreshed",
                aggregate_type="campaign",
                aggregate_id=campaign_id,
                changes={"fields": ["segment_sources", "audience"]},
                payload={
                    "segment_id": str(segment_id),
                    "segment_revision": source.segment_revision,
                    "member_count": source.member_count,
                    "entity_kind": source.entity_kind,
                },
            )
            uow.commit()
            return source

    def detach_segment_source(
        self,
        campaign_id: CampaignId,
        segment_id: SegmentId,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = self._audience_service(uow).detach_segment_source(
                campaign_id,
                segment_id,
            )
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.segment_source_detached",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["segment_sources", "audience"]},
                    payload={"segment_id": str(segment_id)},
                )
            uow.commit()
            return removed

    def segment_sources(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignSegmentSource]:
        with self._runtime.uow_factory() as uow:
            return self._audience_service(uow).segment_sources(campaign_id, page)

    def add_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        *,
        source: str,
        external_ref: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignAttributionReference:
        with self._runtime.uow_factory() as uow:
            reference = self._linkage_service(uow).add_attribution(
                campaign_id,
                target,
                source=source,
                external_ref=external_ref,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.attribution_added",
                aggregate_type="campaign",
                aggregate_id=campaign_id,
                changes={"fields": ["attributions"]},
                payload={
                    "entity_kind": target.kind,
                    "entity_id": str(target.id),
                    "source": reference.source,
                    "external_ref": reference.external_ref,
                },
            )
            uow.commit()
            return reference

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        *,
        source: str,
        external_ref: str | None = None,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = self._linkage_service(uow).remove_attribution(
                campaign_id,
                target,
                source=source,
                external_ref=external_ref,
            )
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.attribution_removed",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["attributions"]},
                    payload={
                        "entity_kind": target.kind,
                        "entity_id": str(target.id),
                        "source": source,
                        "external_ref": external_ref,
                    },
                )
            uow.commit()
            return removed

    def attributions(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignAttributionReference]:
        with self._runtime.uow_factory() as uow:
            return self._linkage_service(uow).attributions(campaign_id, page)

    def link_communication(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
        *,
        role: str = "touchpoint",
        metadata: Mapping[str, object] | None = None,
    ) -> CampaignCommunicationLink:
        with self._runtime.uow_factory() as uow:
            link = self._linkage_service(uow).link_communication(
                campaign_id,
                communication_id,
                role=role,
                actor_id=self._runtime.context.actor_id,
                metadata=metadata,
            )
            self._runtime.record_change(
                uow,
                event_type="campaign.communication_linked",
                aggregate_type="campaign",
                aggregate_id=campaign_id,
                changes={"fields": ["communications"]},
                payload={
                    "communication_id": str(communication_id),
                    "role": link.role,
                },
            )
            uow.commit()
            return link

    def unlink_communication(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
    ) -> bool:
        with self._runtime.uow_factory() as uow:
            removed = self._linkage_service(uow).unlink_communication(
                campaign_id,
                communication_id,
            )
            if removed:
                self._runtime.record_change(
                    uow,
                    event_type="campaign.communication_unlinked",
                    aggregate_type="campaign",
                    aggregate_id=campaign_id,
                    changes={"fields": ["communications"]},
                    payload={"communication_id": str(communication_id)},
                )
            uow.commit()
            return removed

    def communication_links(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CampaignCommunicationLink]:
        with self._runtime.uow_factory() as uow:
            return self._linkage_service(uow).communication_links(campaign_id, page)

    def communications(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest | None = None,
    ) -> Page[CommunicationRecord]:
        with self._runtime.uow_factory() as uow:
            return self._linkage_service(uow).communications_for_campaign(
                campaign_id,
                page,
            )

    def _transition(
        self,
        campaign_id: CampaignId,
        *,
        transition: str,
        event_type: str,
        expected_revision: int | None,
    ) -> Campaign:
        with self._runtime.uow_factory() as uow:
            before = self._capabilities(uow).campaigns.get(campaign_id)
            service = self._service(self._capabilities(uow))
            if transition == "activate":
                campaign = service.activate(
                    campaign_id,
                    expected_revision=expected_revision,
                )
            elif transition == "complete":
                campaign = service.complete(
                    campaign_id,
                    expected_revision=expected_revision,
                )
            elif transition == "archive":
                campaign = service.archive(
                    campaign_id,
                    expected_revision=expected_revision,
                )
            else:
                raise AssertionError(f"unsupported Campaign transition: {transition}")
            if campaign.revision != before.revision:
                self._runtime.record_change(
                    uow,
                    event_type=event_type,
                    aggregate_type="campaign",
                    aggregate_id=campaign.id,
                    changes={"fields": ["status", "updated_at", "revision"]},
                    payload={
                        "status": campaign.status.value,
                        "revision": campaign.revision,
                    },
                )
            uow.commit()
            return campaign

    def _service(self, capabilities: CampaignUnitOfWork) -> CampaignService:
        return CampaignService(
            capabilities.campaigns,
            id_factory=self._runtime.id_factory,
            clock=self._runtime.clock,
        )

    def _linkage_service(self, uow: object) -> CampaignLinkageService:
        if not isinstance(uow, CampaignLinkageUnitOfWork):
            raise IntegrationError(
                "Campaign attribution/communication linkage is not available "
                "for this persistence adapter yet",
                code="campaign.linkage.persistence.unsupported",
            )
        return CampaignLinkageService(
            uow.campaigns,
            uow.campaign_linkage,
            uow.communications,
            uow.segment_query_executor,
            clock=self._runtime.clock,
        )

    def _audience_service(self, uow: object) -> CampaignAudienceService:
        if not isinstance(uow, CampaignUnitOfWork):
            raise IntegrationError(
                "Campaigns are not available for this persistence adapter yet",
                code="campaign.persistence.unsupported",
            )
        if not isinstance(uow, CampaignAudienceUnitOfWork):
            raise IntegrationError(
                "Campaign audiences are not available for this persistence adapter yet",
                code="campaign.audience.persistence.unsupported",
            )
        if not isinstance(uow, SegmentUnitOfWork):
            raise IntegrationError(
                "Campaign Segment sources require Segmentation persistence support",
                code="campaign.segment_source.persistence.unsupported",
            )
        return CampaignAudienceService(
            uow.campaigns,
            uow.campaign_audience,
            uow.segments,
            uow.segment_memberships,
            uow.segment_query_executor,
            clock=self._runtime.clock,
        )

    @staticmethod
    def _capabilities(uow: object) -> CampaignUnitOfWork:
        if not isinstance(uow, CampaignUnitOfWork):
            raise IntegrationError(
                "Campaigns are not available for this persistence adapter yet",
                code="campaign.persistence.unsupported",
            )
        return uow

    @staticmethod
    def _changed_fields(changes: CampaignUpdate) -> tuple[str, ...]:
        return tuple(
            name
            for name in (
                "name",
                "description",
                "starts_at",
                "ends_at",
                "owner_id",
                "metadata",
            )
            if not isinstance(getattr(changes, name), UnsetType)
        )


__all__ = ["CampaignsAPI"]
