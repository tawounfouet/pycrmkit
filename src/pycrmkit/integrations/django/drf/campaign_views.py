"""Opt-in DRF Campaign metadata and lifecycle ViewSet.

All operations authorize before requesting a Campaign from the facade.
No Django ORM objects appear in this transport layer.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from pycrmkit.campaigns import CampaignId, CampaignQuery, CampaignStatus
from pycrmkit.core.ids import EntityId
from pycrmkit.integrations.django.drf.campaign_audience_views import (
    CampaignAudienceActions,
)
from pycrmkit.integrations.django.drf.campaign_security import get_campaign_crm
from pycrmkit.integrations.django.drf.campaign_serializers import (
    CampaignCreateSerializer,
    CampaignFilterSerializer,
    CampaignResponseSerializer,
    CampaignRevisionSerializer,
    CampaignUpdateSerializer,
    campaign_payload,
)
from pycrmkit.integrations.django.drf.pagination import (
    PaginationQuerySerializer,
    page_payload,
)
from pycrmkit.integrations.django.drf.views import CRMViewSet


def _campaign_id(pk: str | None) -> CampaignId:
    if pk is None:
        raise DRFValidationError({"id": ["Campaign id is required"]})
    try:
        return CampaignId(UUID(pk))
    except ValueError as exc:
        raise DRFValidationError({"id": ["must be a valid UUID"]}) from exc


def _validated(serializer: Any) -> dict[str, Any]:
    return cast(dict[str, Any], serializer.validated_data)


def _campaign_response(value: Any) -> Response:
    return Response(CampaignResponseSerializer(campaign_payload(value)).data)


class CampaignViewSet(CampaignAudienceActions, CRMViewSet):
    """Campaign HTTP endpoints guarded by application-host authentication."""

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, NotAuthenticated):
            return Response(
                {"detail": "Campaign authentication required"},
                status=status.HTTP_401_UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )
        response = super().handle_exception(exc)
        if isinstance(exc, DRFValidationError) and response.status_code == 400:
            response.status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        return response

    def list(self, request: Request) -> Response:
        filters = CampaignFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        params = _validated(filters)
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        page_request = pagination.to_domain()
        campaign_status = (
            CampaignStatus(cast(str, params["status"]))
            if "status" in params
            else None
        )
        owner_id = params.get("owner_id")
        include_archived = cast(bool, params.get("include_archived", False))
        scope = {
            "status": campaign_status.value if campaign_status is not None else None,
            "owner_id": str(owner_id) if owner_id is not None else None,
            "include_archived": include_archived,
            "limit": page_request.limit,
            "offset": page_request.offset,
        }
        crm = get_campaign_crm(request, action="campaign.list", scope=scope)
        result = crm.campaigns.list(
            CampaignQuery(
                status=campaign_status,
                owner_id=EntityId(owner_id) if owner_id is not None else None,
                include_archived=include_archived,
            ),
            page_request,
        )
        items = [
            dict(CampaignResponseSerializer(campaign_payload(item)).data)
            for item in result.items
        ]
        return Response(page_payload(result, items))

    def create(self, request: Request) -> Response:
        serializer = CampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = _validated(serializer)
        crm = get_campaign_crm(request, action="campaign.create")
        owner_id = payload.get("owner_id")
        campaign = crm.campaigns.create(
            key=cast(str, payload["key"]),
            name=cast(str, payload["name"]),
            description=cast(str | None, payload.get("description")),
            starts_at=payload.get("starts_at"),
            ends_at=payload.get("ends_at"),
            owner_id=EntityId(owner_id) if owner_id is not None else None,
            metadata=cast(dict[str, object], payload.get("metadata", {})),
        )
        return Response(
            CampaignResponseSerializer(campaign_payload(campaign)).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        crm = get_campaign_crm(
            request, action="campaign.read", campaign_id=str(campaign_id)
        )
        return _campaign_response(crm.campaigns.get(campaign_id))

    def partial_update(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = _validated(serializer)
        crm = get_campaign_crm(
            request, action="campaign.update", campaign_id=str(campaign_id)
        )
        return _campaign_response(
            crm.campaigns.update(
                campaign_id,
                serializer.to_domain(),
                expected_revision=cast(int, payload["expected_revision"]),
            )
        )

    @action(detail=True, methods=["post"])
    def activate(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm = get_campaign_crm(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return _campaign_response(
            crm.campaigns.activate(
                campaign_id,
                expected_revision=cast(
                    int, _validated(serializer)["expected_revision"]
                ),
            )
        )

    @action(detail=True, methods=["post"])
    def complete(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm = get_campaign_crm(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return _campaign_response(
            crm.campaigns.complete(
                campaign_id,
                expected_revision=cast(
                    int, _validated(serializer)["expected_revision"]
                ),
            )
        )

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignRevisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm = get_campaign_crm(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return _campaign_response(
            crm.campaigns.archive(
                campaign_id,
                expected_revision=cast(
                    int, _validated(serializer)["expected_revision"]
                ),
            )
        )


__all__ = ["CampaignViewSet"]
