"""DRF actions for direct Campaign audience and Segment-source membership.

This mixin exposes only the facade and never accesses persistence adapters.
The host-provided Campaign security boundary authorizes each action first.
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
from pycrmkit.integrations.django.drf.campaign_security import get_campaign_crm
from pycrmkit.integrations.django.drf.campaign_serializers import (
    CampaignMemberResponseSerializer,
    CampaignMembersSerializer,
    CampaignRemoveMembersSerializer,
    CampaignSegmentAttachSerializer,
    CampaignSegmentSourceResponseSerializer,
    campaign_member_payload,
    campaign_segment_source_payload,
)
from pycrmkit.integrations.django.drf.pagination import (
    PaginationQuerySerializer,
    page_payload,
)
from pycrmkit.integrations.django.drf.segmentation_serializers import (
    EntityReferenceSerializer,
)
from pycrmkit.segments import SegmentId


def _campaign_id(pk: str | None) -> CampaignId:
    if pk is None:
        raise DRFValidationError({"id": ["Campaign id is required"]})
    try:
        return CampaignId(UUID(pk))
    except ValueError as exc:
        raise DRFValidationError({"id": ["must be a valid UUID"]}) from exc


def _segment_id(raw: str) -> SegmentId:
    try:
        return SegmentId(UUID(raw))
    except ValueError as exc:
        raise DRFValidationError({"segment_id": ["must be a valid UUID"]}) from exc


def _pagination(request: Request) -> Any:
    serializer = PaginationQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.to_domain()


def _source_response(source: Any, *, code: int = 200) -> Response:
    return Response(
        CampaignSegmentSourceResponseSerializer(
            campaign_segment_source_payload(source)
        ).data,
        status=code,
    )


class CampaignAudienceActions:
    """DRF router actions registered by the opt-in CampaignViewSet."""

    @action(detail=True, methods=["get", "post"])
    def members(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        if request.method == "GET":
            page = _pagination(request)
            crm = get_campaign_crm(
                request,
                action="campaign.members.read",
                campaign_id=str(campaign_id),
            )
            members = crm.campaigns.members(campaign_id, page)
            items = [
                dict(
                    CampaignMemberResponseSerializer(
                        campaign_member_payload(member)
                    ).data
                )
                for member in members.items
            ]
            return Response(page_payload(members, items))

        serializer = CampaignMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(dict[str, Any], serializer.validated_data)
        crm = get_campaign_crm(
            request,
            action="campaign.members.write",
            campaign_id=str(campaign_id),
        )
        created = crm.campaigns.add_members(
            campaign_id,
            serializer.references(),
            source=cast(str, payload.get("source", "api")),
            metadata=cast(dict[str, object], payload.get("metadata", {})),
        )
        return Response(
            [
                dict(
                    CampaignMemberResponseSerializer(
                        campaign_member_payload(member)
                    ).data
                )
                for member in created
            ]
        )

    @action(detail=True, methods=["post"], url_path="members/remove")
    def remove_members(
        self,
        request: Request,
        pk: str | None = None,
    ) -> Response:
        campaign_id = _campaign_id(pk)
        serializer = CampaignRemoveMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        crm = get_campaign_crm(
            request,
            action="campaign.members.write",
            campaign_id=str(campaign_id),
        )
        return Response(
            {
                "removed": crm.campaigns.remove_members(
                    campaign_id, serializer.references()
                )
            }
        )

    @action(detail=True, methods=["get"])
    def audience(self, request: Request, pk: str | None = None) -> Response:
        campaign_id = _campaign_id(pk)
        page = _pagination(request)
        crm = get_campaign_crm(
            request,
            action="campaign.members.read",
            campaign_id=str(campaign_id),
        )
        members = crm.campaigns.audience(campaign_id, page)
        items = [
            dict(
                EntityReferenceSerializer(
                    {"kind": entity.kind, "id": entity.id.value}
                ).data
            )
            for entity in members.items
        ]
        return Response(page_payload(members, items))

    @action(detail=True, methods=["get"], url_path="audience/count")
    def audience_count(
        self,
        request: Request,
        pk: str | None = None,
    ) -> Response:
        campaign_id = _campaign_id(pk)
        crm = get_campaign_crm(
            request,
            action="campaign.members.read",
            campaign_id=str(campaign_id),
        )
        return Response({"count": crm.campaigns.audience_count(campaign_id)})

    @action(detail=True, methods=["get", "post"], url_path="segment-sources")
    def segment_sources(
        self,
        request: Request,
        pk: str | None = None,
    ) -> Response:
        campaign_id = _campaign_id(pk)
        if request.method == "GET":
            page = _pagination(request)
            crm = get_campaign_crm(
                request,
                action="campaign.sources.read",
                campaign_id=str(campaign_id),
            )
            sources = crm.campaigns.segment_sources(campaign_id, page)
            items = [
                dict(
                    CampaignSegmentSourceResponseSerializer(
                        campaign_segment_source_payload(source)
                    ).data
                )
                for source in sources.items
            ]
            return Response(page_payload(sources, items))

        serializer = CampaignSegmentAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(dict[str, Any], serializer.validated_data)
        crm = get_campaign_crm(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        created = crm.campaigns.attach_segment_source(
            campaign_id,
            SegmentId(payload["segment_id"]),
            metadata=cast(dict[str, object], payload.get("metadata", {})),
        )
        return _source_response(created, code=status.HTTP_201_CREATED)

    @action(
        detail=True,
        methods=["post"],
        url_path=r"segment-sources/(?P<segment_id>[^/.]+)/refresh",
    )
    def refresh_segment_source(
        self,
        request: Request,
        pk: str | None = None,
        segment_id: str = "",
    ) -> Response:
        campaign_id = _campaign_id(pk)
        segment = _segment_id(segment_id)
        crm = get_campaign_crm(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        return _source_response(
            crm.campaigns.refresh_segment_source(campaign_id, segment)
        )

    @action(
        detail=True,
        methods=["post"],
        url_path=r"segment-sources/(?P<segment_id>[^/.]+)/detach",
    )
    def detach_segment_source(
        self,
        request: Request,
        pk: str | None = None,
        segment_id: str = "",
    ) -> Response:
        campaign_id = _campaign_id(pk)
        segment = _segment_id(segment_id)
        crm = get_campaign_crm(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        return Response({
            "removed": crm.campaigns.detach_segment_source(
                campaign_id, segment
            )
        })


__all__ = ["CampaignAudienceActions"]
