"""Facade-only, opt-in FastAPI Campaign audience and Segment-source endpoints.

Authorization checks precede facade access, including audience cardinality.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from pycrmkit.campaigns import CampaignId
from pycrmkit.integrations.fastapi.campaign_schemas import (
    CampaignMemberResponse,
    CampaignMembersRequest,
    CampaignRemoveMembersRequest,
    CampaignSegmentAttachRequest,
    CampaignSegmentSourceResponse,
)
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.integrations.fastapi.errors import (
    LIST_ERROR_RESPONSES,
    MUTATION_ERROR_RESPONSES,
)
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import EntityReferenceSchema
from pycrmkit.segments import SegmentId

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Authenticated Campaign principal required"},
    403: {"description": "Campaign permission denied"},
}
_LIST_ERRORS = {**LIST_ERROR_RESPONSES, **_AUTH_ERRORS}
_MUTATION_ERRORS = {**MUTATION_ERROR_RESPONSES, **_AUTH_ERRORS}


def create_campaign_audience_router(access: CampaignHTTPAccess) -> APIRouter:
    """Build subordinate routes mounted under an already secured /campaigns."""
    if not isinstance(access, CampaignHTTPAccess):
        raise TypeError("Campaign audience router requires CampaignHTTPAccess")

    router = APIRouter()

    @router.get(
        "/{campaign_id}/members",
        response_model=PageResponse[CampaignMemberResponse],
        responses=_LIST_ERRORS,
    )
    def list_members(
        campaign_id: UUID,
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[CampaignMemberResponse]:
        crm = access.crm_for(
            request,
            action="campaign.members.read",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.members(CampaignId(campaign_id), page.to_domain())
        return PageResponse[CampaignMemberResponse].from_page(
            result, CampaignMemberResponse.from_domain
        )

    @router.post(
        "/{campaign_id}/members",
        response_model=list[CampaignMemberResponse],
        responses=_MUTATION_ERRORS,
    )
    def add_members(
        campaign_id: UUID,
        payload: CampaignMembersRequest,
        request: Request,
    ) -> list[CampaignMemberResponse]:
        crm = access.crm_for(
            request,
            action="campaign.members.write",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.add_members(
            CampaignId(campaign_id),
            payload.references(),
            source=payload.source,
            metadata=payload.metadata,
        )
        return [CampaignMemberResponse.from_domain(member) for member in result]

    @router.post(
        "/{campaign_id}/members/remove",
        response_model=dict[str, int],
        responses=_MUTATION_ERRORS,
    )
    def remove_members(
        campaign_id: UUID,
        payload: CampaignRemoveMembersRequest,
        request: Request,
    ) -> dict[str, int]:
        crm = access.crm_for(
            request,
            action="campaign.members.write",
            campaign_id=str(campaign_id),
        )
        return {
            "removed": crm.campaigns.remove_members(
                CampaignId(campaign_id), payload.references()
            )
        }

    @router.get(
        "/{campaign_id}/audience",
        response_model=PageResponse[EntityReferenceSchema],
        responses=_LIST_ERRORS,
    )
    def list_audience(
        campaign_id: UUID,
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[EntityReferenceSchema]:
        crm = access.crm_for(
            request,
            action="campaign.members.read",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.audience(CampaignId(campaign_id), page.to_domain())
        return PageResponse[EntityReferenceSchema].from_page(
            result, EntityReferenceSchema.from_domain
        )

    @router.get(
        "/{campaign_id}/audience/count",
        response_model=dict[str, int],
        responses=_LIST_ERRORS,
    )
    def audience_count(campaign_id: UUID, request: Request) -> dict[str, int]:
        crm = access.crm_for(
            request,
            action="campaign.members.read",
            campaign_id=str(campaign_id),
        )
        return {"count": crm.campaigns.audience_count(CampaignId(campaign_id))}

    @router.get(
        "/{campaign_id}/segment-sources",
        response_model=PageResponse[CampaignSegmentSourceResponse],
        responses=_LIST_ERRORS,
    )
    def list_segment_sources(
        campaign_id: UUID,
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[CampaignSegmentSourceResponse]:
        crm = access.crm_for(
            request,
            action="campaign.sources.read",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.segment_sources(
            CampaignId(campaign_id), page.to_domain()
        )
        return PageResponse[CampaignSegmentSourceResponse].from_page(
            result, CampaignSegmentSourceResponse.from_domain
        )

    @router.post(
        "/{campaign_id}/segment-sources",
        status_code=status.HTTP_201_CREATED,
        response_model=CampaignSegmentSourceResponse,
        responses=_MUTATION_ERRORS,
    )
    def attach_segment_source(
        campaign_id: UUID,
        payload: CampaignSegmentAttachRequest,
        request: Request,
    ) -> CampaignSegmentSourceResponse:
        crm = access.crm_for(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        attached = crm.campaigns.attach_segment_source(
            CampaignId(campaign_id),
            SegmentId(payload.segment_id),
            metadata=payload.metadata,
        )
        return CampaignSegmentSourceResponse.from_domain(attached)

    @router.post(
        "/{campaign_id}/segment-sources/{segment_id}/refresh",
        response_model=CampaignSegmentSourceResponse,
        responses=_MUTATION_ERRORS,
    )
    def refresh_segment_source(
        campaign_id: UUID,
        segment_id: UUID,
        request: Request,
    ) -> CampaignSegmentSourceResponse:
        crm = access.crm_for(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        updated = crm.campaigns.refresh_segment_source(
            CampaignId(campaign_id), SegmentId(segment_id)
        )
        return CampaignSegmentSourceResponse.from_domain(updated)

    @router.post(
        "/{campaign_id}/segment-sources/{segment_id}/detach",
        response_model=dict[str, bool],
        responses=_MUTATION_ERRORS,
    )
    def detach_segment_source(
        campaign_id: UUID,
        segment_id: UUID,
        request: Request,
    ) -> dict[str, bool]:
        crm = access.crm_for(
            request,
            action="campaign.sources.write",
            campaign_id=str(campaign_id),
        )
        return {
            "removed": crm.campaigns.detach_segment_source(
                CampaignId(campaign_id), SegmentId(segment_id)
            )
        }

    return router


__all__ = ["create_campaign_audience_router"]
