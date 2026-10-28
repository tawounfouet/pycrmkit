"""Opt-in, facade-backed FastAPI Campaign metadata and lifecycle endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from pycrmkit.campaigns import CampaignId, CampaignQuery, CampaignStatus
from pycrmkit.core.ids import EntityId
from pycrmkit.integrations.fastapi.campaign_schemas import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignRevisionRequest,
    CampaignUpdateRequest,
)
from pycrmkit.integrations.fastapi.campaign_security import CampaignHTTPAccess
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.routers.campaign_audience import (
    create_campaign_audience_router,
)

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Verified Campaign principal is required"},
    403: {"description": "Campaign action or resource access is denied"},
}


def create_campaigns_router(access: CampaignHTTPAccess) -> APIRouter:
    """Build Campaign HTTP routes only with an explicit security boundary."""
    if not isinstance(access, CampaignHTTPAccess):
        raise TypeError("Campaign router requires CampaignHTTPAccess")

    router = APIRouter(prefix="/campaigns", tags=["campaigns"])

    @router.post(
        "",
        status_code=status.HTTP_201_CREATED,
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def create_campaign(
        payload: CampaignCreateRequest,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(request, action="campaign.create")
        created = crm.campaigns.create(
            key=payload.key,
            name=payload.name,
            description=payload.description,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            owner_id=EntityId(payload.owner_id) if payload.owner_id else None,
            metadata=payload.metadata,
        )
        return CampaignResponse.from_domain(created)

    @router.get(
        "",
        response_model=PageResponse[CampaignResponse],
        responses=_AUTH_ERRORS,
    )
    def list_campaigns(
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
        status: CampaignStatus | None = None,
        owner_id: UUID | None = None,
        include_archived: bool = False,
    ) -> PageResponse[CampaignResponse]:
        scope = {
            "status": status.value if status is not None else None,
            "owner_id": str(owner_id) if owner_id is not None else None,
            "include_archived": include_archived,
            "limit": page.limit,
            "offset": page.offset,
        }
        crm = access.crm_for(request, action="campaign.list", scope=scope)
        result = crm.campaigns.list(
            CampaignQuery(
                status=status,
                owner_id=EntityId(owner_id) if owner_id else None,
                include_archived=include_archived,
            ),
            page.to_domain(),
        )
        return PageResponse[CampaignResponse].from_page(
            result, CampaignResponse.from_domain
        )

    @router.get(
        "/{campaign_id}",
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def get_campaign(
        campaign_id: UUID,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(
            request, action="campaign.read", campaign_id=str(campaign_id)
        )
        return CampaignResponse.from_domain(
            crm.campaigns.get(CampaignId(campaign_id))
        )

    @router.patch(
        "/{campaign_id}",
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def update_campaign(
        campaign_id: UUID,
        payload: CampaignUpdateRequest,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(
            request, action="campaign.update", campaign_id=str(campaign_id)
        )
        return CampaignResponse.from_domain(
            crm.campaigns.update(
                CampaignId(campaign_id),
                payload.to_domain(),
                expected_revision=payload.expected_revision,
            )
        )

    @router.post(
        "/{campaign_id}/activate",
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def activate_campaign(
        campaign_id: UUID,
        payload: CampaignRevisionRequest,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return CampaignResponse.from_domain(
            crm.campaigns.activate(
                CampaignId(campaign_id),
                expected_revision=payload.expected_revision,
            )
        )

    @router.post(
        "/{campaign_id}/complete",
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def complete_campaign(
        campaign_id: UUID,
        payload: CampaignRevisionRequest,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return CampaignResponse.from_domain(
            crm.campaigns.complete(
                CampaignId(campaign_id),
                expected_revision=payload.expected_revision,
            )
        )

    @router.post(
        "/{campaign_id}/archive",
        response_model=CampaignResponse,
        responses=_AUTH_ERRORS,
    )
    def archive_campaign(
        campaign_id: UUID,
        payload: CampaignRevisionRequest,
        request: Request,
    ) -> CampaignResponse:
        crm = access.crm_for(
            request, action="campaign.lifecycle", campaign_id=str(campaign_id)
        )
        return CampaignResponse.from_domain(
            crm.campaigns.archive(
                CampaignId(campaign_id),
                expected_revision=payload.expected_revision,
            )
        )

    router.include_router(create_campaign_audience_router(access))
    return router


__all__ = ["create_campaigns_router"]
