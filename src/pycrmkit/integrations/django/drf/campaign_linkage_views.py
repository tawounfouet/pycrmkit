"""Opt-in DRF Campaign attribution and Communication linkage actions.

The transport exposes only link metadata, never CommunicationRecord content.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from pycrmkit.campaigns import CampaignId
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.integrations.django.drf.campaign_security import get_campaign_crm
from pycrmkit.integrations.django.drf.campaign_serializers import (
    CampaignAttributionRemoveSerializer,
    CampaignAttributionResponseSerializer,
    CampaignAttributionSerializer,
    CampaignCommunicationLinkResponseSerializer,
    CampaignCommunicationLinkSerializer,
    CampaignCommunicationUnlinkSerializer,
    campaign_attribution_payload,
    campaign_communication_link_payload,
)
from pycrmkit.integrations.django.drf.pagination import (
    PaginationQuerySerializer,
    page_payload,
)
from pycrmkit.integrations.django.drf.segmentation_serializers import (
    _entity_reference,
)


def _campaign_id(pk: str | None) -> CampaignId:
    if pk is None:
        raise DRFValidationError({"id": ["Campaign id is required"]})
    try:
        return CampaignId(UUID(pk))
    except ValueError as exc:
        raise DRFValidationError({"id": ["must be a valid UUID"]}) from exc


def _data(serializer: Any) -> dict[str, Any]:
    return cast(dict[str, Any], serializer.validated_data)


def _page(request: Request) -> Any:
    serializer = PaginationQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.to_domain()


class CampaignLinkageActions:
    """DRF actions guarded by action-specific host Campaign authorization."""

    @action(detail=True, methods=["get", "post"])
    def attributions(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        if request.method == "GET":
            crm = get_campaign_crm(
                request,
                action="campaign.attribution.read",
                campaign_id=str(campaign_id),
            )
            result = crm.campaigns.attributions(campaign_id, _page(request))
            items = [
                dict(
                    CampaignAttributionResponseSerializer(
                        campaign_attribution_payload(item)
                    ).data
                )
                for item in result.items
            ]
            return Response(page_payload(result, items))

        serializer = CampaignAttributionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _data(serializer)
        crm = get_campaign_crm(
            request,
            action="campaign.attribution.write",
            campaign_id=str(campaign_id),
        )
        created = crm.campaigns.add_attribution(
            campaign_id,
            _entity_reference(data["target"]),
            source=cast(str, data["source"]),
            external_ref=cast(str | None, data.get("external_ref")),
            metadata=cast(dict[str, object], data.get("metadata", {})),
        )
        return Response(
            CampaignAttributionResponseSerializer(
                campaign_attribution_payload(created)
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="attributions/remove")
    def remove_attribution(
        self, request: Request, pk: str | None = None
    ) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignAttributionRemoveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _data(serializer)
        crm = get_campaign_crm(
            request,
            action="campaign.attribution.write",
            campaign_id=str(campaign_id),
        )
        removed = crm.campaigns.remove_attribution(
            campaign_id,
            _entity_reference(data["target"]),
            source=cast(str, data["source"]),
            external_ref=cast(str | None, data.get("external_ref")),
        )
        return Response({"removed": removed})

    @action(detail=True, methods=["get", "post"], url_path="communication-links")
    def communication_links(
        self, request: Request, pk: str | None = None
    ) -> Response:
        campaign_id = _campaign_id(pk)
        if request.method == "GET":
            crm = get_campaign_crm(
                request,
                action="campaign.communications.link",
                campaign_id=str(campaign_id),
            )
            result = crm.campaigns.communication_links(
                campaign_id, _page(request)
            )
            items = [
                dict(
                    CampaignCommunicationLinkResponseSerializer(
                        campaign_communication_link_payload(item)
                    ).data
                )
                for item in result.items
            ]
            return Response(page_payload(result, items))

        serializer = CampaignCommunicationLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _data(serializer)
        crm = get_campaign_crm(
            request,
            action="campaign.communications.link",
            campaign_id=str(campaign_id),
        )
        created = crm.campaigns.link_communication(
            campaign_id,
            CommunicationRecordId(data["communication_id"]),
            role=cast(str, data.get("role", "touchpoint")),
            metadata=cast(dict[str, object], data.get("metadata", {})),
        )
        return Response(
            CampaignCommunicationLinkResponseSerializer(
                campaign_communication_link_payload(created)
            ).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True, methods=["post"], url_path="communication-links/remove"
    )
    def unlink_communication(
        self, request: Request, pk: str | None = None
    ) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignCommunicationUnlinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm = get_campaign_crm(
            request,
            action="campaign.communications.link",
            campaign_id=str(campaign_id),
        )
        removed = crm.campaigns.unlink_communication(
            campaign_id,
            CommunicationRecordId(_data(serializer)["communication_id"]),
        )
        return Response({"removed": removed})


__all__ = ["CampaignLinkageActions"]
