"""Campaigns facade namespace."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignQuery,
    CampaignService,
    CampaignUnitOfWork,
    CampaignUpdate,
    UnsetType,
)
from pycrmkit.core.ids import EntityId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import IntegrationError
from pycrmkit.facade._runtime import CRMRuntime


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
            method = getattr(service, transition)
            campaign = method(campaign_id, expected_revision=expected_revision)
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
