"""Django CampaignRepository with optimistic revision control."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from pycrmkit.campaigns import (
    Campaign,
    CampaignId,
    CampaignQuery,
    CampaignStatus,
    normalize_campaign_key,
)
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.exceptions import ConflictError, DuplicateError, NotFoundError
from pycrmkit.integrations.django.campaign_codec import (
    campaign_from_model,
    campaign_to_model,
)
from pycrmkit.integrations.django.models import CampaignModel


_T = TypeVar("_T")


def _page(
    queryset: QuerySet[Any], page: OffsetPageRequest, mapper: Callable[[Any], _T]
) -> Page[_T]:
    total = queryset.count()
    return Page(
        items=tuple(mapper(row) for row in queryset[page.offset : page.offset + page.limit]),
        limit=page.limit,
        offset=page.offset,
        total=total,
    )


class DjangoCampaignRepository:
    """Map the domain Campaign aggregate into Django persistence only."""

    def get(self, campaign_id: CampaignId) -> Campaign:
        found = self.find(campaign_id)
        if found is None:
            raise NotFoundError(
                "Campaign not found",
                code="campaign.not_found",
                context={"campaign_id": str(campaign_id)},
            )
        return found

    def find(self, campaign_id: CampaignId) -> Campaign | None:
        model = CampaignModel.objects.filter(pk=str(campaign_id)).first()
        return None if model is None else campaign_from_model(model)

    def find_by_key(self, key: str) -> Campaign | None:
        model = CampaignModel.objects.filter(
            key=normalize_campaign_key(key)
        ).first()
        return None if model is None else campaign_from_model(model)

    def save(self, campaign: Campaign) -> None:
        by_key = self.find_by_key(campaign.key)
        if by_key is not None and by_key.id != campaign.id:
            raise self._key_duplicate(campaign.key)

        current = CampaignModel.objects.filter(pk=str(campaign.id)).first()
        if current is None:
            if campaign.revision != 1:
                raise self._revision_conflict(expected=1, actual=campaign.revision)
            try:
                with transaction.atomic():
                    campaign_to_model(campaign).save(force_insert=True)
            except IntegrityError as error:
                if CampaignModel.objects.filter(key=campaign.key).exclude(
                    pk=str(campaign.id)
                ).exists():
                    raise self._key_duplicate(campaign.key) from error
                raise self._revision_conflict(
                    expected=1, actual=campaign.revision
                ) from error
            return

        revision = current.revision
        if campaign.revision == revision:
            if self._same_state(campaign, campaign_from_model(current)):
                return
            raise self._revision_conflict(
                expected=revision + 1, actual=campaign.revision
            )
        if campaign.revision != revision + 1:
            raise self._revision_conflict(
                expected=revision + 1, actual=campaign.revision
            )

        try:
            with transaction.atomic():
                changed = CampaignModel.objects.filter(
                    pk=str(campaign.id), revision=revision
                ).update(
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
        except IntegrityError as error:
            if CampaignModel.objects.filter(key=campaign.key).exclude(
                pk=str(campaign.id)
            ).exists():
                raise self._key_duplicate(campaign.key) from error
            raise self._revision_conflict(
                expected=revision + 1, actual=campaign.revision
            ) from error
        if changed != 1:
            raise self._revision_conflict(
                expected=revision + 1, actual=campaign.revision
            )

    def search(
        self, query: CampaignQuery, page: OffsetPageRequest
    ) -> Page[Campaign]:
        queryset = CampaignModel.objects.all()
        if not query.include_archived:
            queryset = queryset.exclude(status=CampaignStatus.ARCHIVED.value)
        if query.status is not None:
            queryset = queryset.filter(status=query.status.value)
        if query.owner_id is not None:
            queryset = queryset.filter(owner_id=str(query.owner_id))
        return _page(queryset.order_by("created_at", "id"), page, campaign_from_model)

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
    def _key_duplicate(key: str) -> DuplicateError:
        return DuplicateError(
            "Campaign key already exists",
            code="campaign.key.duplicate",
            context={"key": key},
        )

    @staticmethod
    def _revision_conflict(*, expected: int, actual: int) -> ConflictError:
        return ConflictError(
            "campaign revision has changed",
            code="campaign.revision.conflict",
            context={"expected": expected, "actual": actual},
        )


__all__ = ["DjangoCampaignRepository"]
