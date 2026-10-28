"""Django Campaign attribution and Communication-link repository."""

from __future__ import annotations

import unicodedata

from django.db import IntegrityError, transaction

from pycrmkit.campaigns import (
    CampaignAttributionReference,
    CampaignCommunicationLink,
    CampaignId,
    normalize_campaign_external_ref,
)
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError
from pycrmkit.integrations.django.campaign_codec import (
    campaign_attribution_from_model,
    campaign_attribution_to_model,
    campaign_communication_link_from_model,
    campaign_communication_link_to_model,
)
from pycrmkit.integrations.django.campaign_repositories import _page
from pycrmkit.integrations.django.models import (
    CampaignAttributionModel,
    CampaignCommunicationLinkModel,
)


def _source_key(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", value).strip().split()
    ).casefold()


def _external_ref_to_db(value: str | None) -> str:
    normalized = normalize_campaign_external_ref(value)
    return "" if normalized is None else normalized


class DjangoCampaignLinkageRepository:
    """Campaign-owned linkage rows; Communication records remain independent."""

    def add_attribution(
        self, reference: CampaignAttributionReference
    ) -> CampaignAttributionReference:
        if self._attribution_queryset(
            reference.campaign_id,
            reference.target,
            reference.source,
            reference.external_ref,
        ).exists():
            raise self._attribution_duplicate(reference)
        try:
            with transaction.atomic():
                campaign_attribution_to_model(reference).save(force_insert=True)
        except IntegrityError as error:
            raise self._attribution_duplicate(reference) from error
        return reference

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ) -> bool:
        deleted, _ = self._attribution_queryset(
            campaign_id, target, source, external_ref
        ).delete()
        return deleted > 0

    def list_attributions(
        self, campaign_id: CampaignId, page: OffsetPageRequest
    ) -> Page[CampaignAttributionReference]:
        rows = CampaignAttributionModel.objects.filter(
            campaign_id=str(campaign_id)
        ).order_by(
            "recorded_at",
            "source",
            "target_kind",
            "target_id",
            "external_ref",
            "id",
        )
        return _page(rows, page, campaign_attribution_from_model)

    def add_communication_link(
        self, link: CampaignCommunicationLink
    ) -> CampaignCommunicationLink:
        if self._link_queryset(link.campaign_id, link.communication_id).exists():
            raise self._link_duplicate(link)
        try:
            with transaction.atomic():
                campaign_communication_link_to_model(link).save(force_insert=True)
        except IntegrityError as error:
            raise self._link_duplicate(link) from error
        return link

    def remove_communication_link(
        self, campaign_id: CampaignId, communication_id: CommunicationRecordId
    ) -> bool:
        deleted, _ = self._link_queryset(campaign_id, communication_id).delete()
        return deleted > 0

    def list_communication_links(
        self, campaign_id: CampaignId, page: OffsetPageRequest
    ) -> Page[CampaignCommunicationLink]:
        rows = CampaignCommunicationLinkModel.objects.filter(
            campaign_id=str(campaign_id)
        ).order_by("linked_at", "communication_id", "id")
        return _page(rows, page, campaign_communication_link_from_model)

    @staticmethod
    def _attribution_queryset(
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ):
        return CampaignAttributionModel.objects.filter(
            campaign_id=str(campaign_id),
            target_kind=target.kind,
            target_id=str(target.id),
            source=_source_key(source),
            external_ref=_external_ref_to_db(external_ref),
        )

    @staticmethod
    def _link_queryset(campaign_id: CampaignId, communication_id: CommunicationRecordId):
        return CampaignCommunicationLinkModel.objects.filter(
            campaign_id=str(campaign_id),
            communication_id=str(communication_id),
        )

    @staticmethod
    def _attribution_duplicate(
        reference: CampaignAttributionReference,
    ) -> DuplicateError:
        return DuplicateError(
            "Campaign attribution reference already exists",
            code="campaign.attribution.duplicate",
            context={
                "campaign_id": str(reference.campaign_id),
                "entity_kind": reference.target.kind,
                "entity_id": str(reference.target.id),
                "source": reference.source,
                "external_ref": reference.external_ref,
            },
        )

    @staticmethod
    def _link_duplicate(link: CampaignCommunicationLink) -> DuplicateError:
        return DuplicateError(
            "Campaign communication link already exists",
            code="campaign.communication_link.duplicate",
            context={
                "campaign_id": str(link.campaign_id),
                "communication_id": str(link.communication_id),
            },
        )


__all__ = ["DjangoCampaignLinkageRepository"]
