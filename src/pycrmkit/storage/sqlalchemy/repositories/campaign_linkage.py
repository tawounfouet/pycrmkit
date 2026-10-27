"""SQLAlchemy CampaignLinkageRepository implementation."""

from __future__ import annotations

import unicodedata

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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
from pycrmkit.storage.sqlalchemy.campaign_codec import (
    campaign_attribution_from_model,
    campaign_attribution_to_model,
    campaign_communication_link_from_model,
    campaign_communication_link_to_model,
)
from pycrmkit.storage.sqlalchemy.models.campaign import (
    CampaignAttributionModel,
    CampaignCommunicationLinkModel,
)
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


def _source_key(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", value).strip().split()
    ).casefold()


def _external_ref_to_db(value: str | None) -> str:
    normalized = normalize_campaign_external_ref(value)
    return "" if normalized is None else normalized


class SQLAlchemyCampaignLinkageRepository:
    """Session-scoped Campaign attribution and communication linkage storage."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_attribution(
        self,
        reference: CampaignAttributionReference,
    ) -> CampaignAttributionReference:
        if self._attribution_exists(
            reference.campaign_id,
            reference.target,
            reference.source,
            reference.external_ref,
        ):
            raise DuplicateError(
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
        self.session.add(campaign_attribution_to_model(reference))
        return reference

    def remove_attribution(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ) -> bool:
        normalized_source = _source_key(source)
        normalized_external_ref = _external_ref_to_db(external_ref)
        predicate = (
            CampaignAttributionModel.campaign_id == str(campaign_id),
            CampaignAttributionModel.target_kind == target.kind,
            CampaignAttributionModel.target_id == str(target.id),
            CampaignAttributionModel.source == normalized_source,
            CampaignAttributionModel.external_ref == normalized_external_ref,
        )
        existing = self.session.scalar(
            select(CampaignAttributionModel.id).where(*predicate)
        )
        if existing is None:
            return False
        self.session.execute(
            delete(CampaignAttributionModel).where(*predicate)
        )
        return True

    def list_attributions(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignAttributionReference]:
        statement = (
            select(CampaignAttributionModel)
            .where(
                CampaignAttributionModel.campaign_id == str(campaign_id)
            )
            .order_by(
                CampaignAttributionModel.recorded_at.asc(),
                CampaignAttributionModel.source.asc(),
                CampaignAttributionModel.target_kind.asc(),
                CampaignAttributionModel.target_id.asc(),
                CampaignAttributionModel.external_ref.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            campaign_attribution_from_model,
        )

    def add_communication_link(
        self,
        link: CampaignCommunicationLink,
    ) -> CampaignCommunicationLink:
        existing = self.session.scalar(
            select(CampaignCommunicationLinkModel.id).where(
                CampaignCommunicationLinkModel.campaign_id
                == str(link.campaign_id),
                CampaignCommunicationLinkModel.communication_id
                == str(link.communication_id),
            )
        )
        if existing is not None:
            raise DuplicateError(
                "Campaign communication link already exists",
                code="campaign.communication_link.duplicate",
                context={
                    "campaign_id": str(link.campaign_id),
                    "communication_id": str(link.communication_id),
                },
            )
        self.session.add(campaign_communication_link_to_model(link))
        return link

    def remove_communication_link(
        self,
        campaign_id: CampaignId,
        communication_id: CommunicationRecordId,
    ) -> bool:
        predicate = (
            CampaignCommunicationLinkModel.campaign_id == str(campaign_id),
            CampaignCommunicationLinkModel.communication_id
            == str(communication_id),
        )
        existing = self.session.scalar(
            select(CampaignCommunicationLinkModel.id).where(*predicate)
        )
        if existing is None:
            return False
        self.session.execute(
            delete(CampaignCommunicationLinkModel).where(*predicate)
        )
        return True

    def list_communication_links(
        self,
        campaign_id: CampaignId,
        page: OffsetPageRequest,
    ) -> Page[CampaignCommunicationLink]:
        statement = (
            select(CampaignCommunicationLinkModel)
            .where(
                CampaignCommunicationLinkModel.campaign_id
                == str(campaign_id)
            )
            .order_by(
                CampaignCommunicationLinkModel.linked_at.asc(),
                CampaignCommunicationLinkModel.communication_id.asc(),
            )
        )
        return page_models(
            self.session,
            statement,
            page,
            campaign_communication_link_from_model,
        )

    def _attribution_exists(
        self,
        campaign_id: CampaignId,
        target: EntityReference,
        source: str,
        external_ref: str | None,
    ) -> bool:
        return (
            self.session.scalar(
                select(CampaignAttributionModel.id).where(
                    CampaignAttributionModel.campaign_id
                    == str(campaign_id),
                    CampaignAttributionModel.target_kind == target.kind,
                    CampaignAttributionModel.target_id == str(target.id),
                    CampaignAttributionModel.source == _source_key(source),
                    CampaignAttributionModel.external_ref
                    == _external_ref_to_db(external_ref),
                )
            )
            is not None
        )


__all__ = ["SQLAlchemyCampaignLinkageRepository"]
