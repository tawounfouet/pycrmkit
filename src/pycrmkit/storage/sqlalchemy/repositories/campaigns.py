"""SQLAlchemy CampaignRepository implementation."""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignQuery,
    CampaignStatus,
    normalize_campaign_key,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.storage.sqlalchemy.campaign_codec import (
    campaign_from_model,
    campaign_to_model,
)
from pycrmkit.storage.sqlalchemy.models.campaign import CampaignModel
from pycrmkit.storage.sqlalchemy.repositories._helpers import page_models


class SQLAlchemyCampaignRepository:
    """Session-scoped SQLAlchemy adapter for Campaign metadata."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, campaign_id: CampaignId) -> Campaign:
        campaign = self.find(campaign_id)
        if campaign is None:
            raise NotFoundError(
                "Campaign not found",
                code="campaign.not_found",
                context={"campaign_id": str(campaign_id)},
            )
        return campaign

    def find(self, campaign_id: CampaignId) -> Campaign | None:
        model = self.session.get(CampaignModel, str(campaign_id))
        return None if model is None else campaign_from_model(model)

    def find_by_key(self, key: str) -> Campaign | None:
        normalized = normalize_campaign_key(key)
        model = self.session.scalar(
            select(CampaignModel).where(CampaignModel.key == normalized)
        )
        return None if model is None else campaign_from_model(model)

    def save(self, campaign: Campaign) -> None:
        by_key = self.find_by_key(campaign.key)
        if by_key is not None and by_key.id != campaign.id:
            raise DuplicateError(
                "Campaign key already exists",
                code="campaign.key.duplicate",
                context={"key": campaign.key},
            )

        current = self.session.get(CampaignModel, str(campaign.id))
        if current is None:
            if campaign.revision != 1:
                raise self._revision_conflict(
                    expected=1,
                    actual=campaign.revision,
                )
            self.session.add(campaign_to_model(campaign))
            return

        current_revision = current.revision
        if campaign.revision == current_revision:
            if self._same_state(campaign, campaign_from_model(current)):
                return
            raise self._revision_conflict(
                expected=current_revision + 1,
                actual=campaign.revision,
            )

        if campaign.revision != current_revision + 1:
            raise self._revision_conflict(
                expected=current_revision + 1,
                actual=campaign.revision,
            )

        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(CampaignModel)
            .where(
                CampaignModel.id == str(campaign.id),
                CampaignModel.revision == current_revision,
            )
            .values(
                key=campaign.key,
                name=campaign.name,
                description=campaign.description,
                status=campaign.status.value,
                starts_at=campaign.starts_at,
                ends_at=campaign.ends_at,
                owner_id=(
                    str(campaign.owner_id)
                    if campaign.owner_id is not None
                    else None
                ),
                revision=campaign.revision,
                metadata_json=dict(campaign.metadata),
                archived_at=campaign.archived_at,
                created_at=campaign.created_at,
                updated_at=campaign.updated_at,
            )
                .execution_options(synchronize_session=False)
            ),
        )
        if result.rowcount != 1:
            self.session.expire(current)
            raise self._revision_conflict(
                expected=current_revision + 1,
                actual=campaign.revision,
            )
        self.session.expire(current)

    def search(
        self,
        query: CampaignQuery,
        page: OffsetPageRequest,
    ) -> Page[Campaign]:
        statement = select(CampaignModel)
        if not query.include_archived:
            statement = statement.where(
                CampaignModel.status != CampaignStatus.ARCHIVED.value
            )
        if query.status is not None:
            statement = statement.where(
                CampaignModel.status == query.status.value
            )
        if query.owner_id is not None:
            statement = statement.where(
                CampaignModel.owner_id == str(query.owner_id)
            )
        statement = statement.order_by(
            CampaignModel.created_at.asc(),
            CampaignModel.id.asc(),
        )
        return page_models(
            self.session,
            statement,
            page,
            campaign_from_model,
        )

    @staticmethod
    def _same_state(left: Campaign, right: Campaign) -> bool:
        return (
            left.id == right.id
            and left.created_at == right.created_at
            and left.updated_at == right.updated_at
            and left.key == right.key
            and left.name == right.name
            and left.description == right.description
            and left.status is right.status
            and left.starts_at == right.starts_at
            and left.ends_at == right.ends_at
            and left.owner_id == right.owner_id
            and left.revision == right.revision
            and left.metadata == right.metadata
            and left.archived_at == right.archived_at
        )

    @staticmethod
    def _revision_conflict(*, expected: int, actual: int) -> ConflictError:
        return ConflictError(
            "campaign revision has changed",
            code="campaign.revision.conflict",
            context={
                "expected": expected,
                "actual": actual,
            },
        )


__all__ = ["SQLAlchemyCampaignRepository"]
