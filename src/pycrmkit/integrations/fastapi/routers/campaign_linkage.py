"""Opt-in FastAPI Campaign attribution and Communication-link endpoints.

Only metadata is returned: the CommunicationRecord body is NEVER exposed here.
Every action is checked against the host-authenticated Campaign security policy.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from pycrmkit.campaigns import CampaignId
from pycrmkit.communication import CommunicationRecordId
from pycrmkit.integrations.fastapi.campaign_schemas import (
    CampaignAttributionRemoveRequest,
    CampaignAttributionRequest,
    CampaignAttributionResponse,
    CampaignCommunicationLinkRequest,
    CampaignCommunicationLinkResponse,
    CampaignCommunicationUnlinkRequest,
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

_AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Authenticated Campaign principal required"},
    403: {"description": "Campaign permission denied"},
}
_LIST_ERRORS: dict[int | str, dict[str, Any]] = {
    **LIST_ERROR_RESPONSES,
    **_AUTH_ERRORS,
}
_MUTATION_ERRORS: dict[int | str, dict[str, Any]] = {
    **MUTATION_ERROR_RESPONSES,
    **_AUTH_ERRORS,
}


def create_campaign_linkage_router(access: CampaignHTTPAccess) -> APIRouter:
    """Create a facade-backed router; never enable it without the security bridge."""
    if not isinstance(access, CampaignHTTPAccess):
        raise TypeError("Campaign linkage router requires CampaignHTTPAccess")

    router = APIRouter()

    @router.get(
        "/{campaign_id}/attributions",
        response_model=PageResponse[CampaignAttributionResponse],
        responses=_LIST_ERRORS,
    )
    def list_attributions(
        campaign_id: UUID,
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[CampaignAttributionResponse]:
        crm = access.crm_for(
            request,
            action="campaign.attribution.read",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.attributions(
            CampaignId(campaign_id), page.to_domain()
        )
        return PageResponse[CampaignAttributionResponse].from_page(
            result, CampaignAttributionResponse.from_domain
        )

    @router.post(
        "/{campaign_id}/attributions",
        response_model=CampaignAttributionResponse,
        status_code=status.HTTP_201_CREATED,
        responses=_MUTATION_ERRORS,
    )
    def add_attribution(
        campaign_id: UUID,
        payload: CampaignAttributionRequest,
        request: Request,
    ) -> CampaignAttributionResponse:
        crm = access.crm_for(
            request,
            action="campaign.attribution.write",
            campaign_id=str(campaign_id),
        )
        created = crm.campaigns.add_attribution(
            CampaignId(campaign_id),
            payload.target.to_domain(),
            source=payload.source,
            external_ref=payload.external_ref,
            metadata=payload.metadata,
        )
        return CampaignAttributionResponse.from_domain(created)

    @router.post(
        "/{campaign_id}/attributions/remove",
        response_model=dict[str, bool],
        responses=_MUTATION_ERRORS,
    )
    def remove_attribution(
        campaign_id: UUID,
        payload: CampaignAttributionRemoveRequest,
        request: Request,
    ) -> dict[str, bool]:
        crm = access.crm_for(
            request,
            action="campaign.attribution.write",
            campaign_id=str(campaign_id),
        )
        return {
            "removed": crm.campaigns.remove_attribution(
                CampaignId(campaign_id),
                payload.target.to_domain(),
                source=payload.source,
                external_ref=payload.external_ref,
            )
        }

    @router.get(
        "/{campaign_id}/communication-links",
        response_model=PageResponse[CampaignCommunicationLinkResponse],
        responses=_LIST_ERRORS,
    )
    def list_communication_links(
        campaign_id: UUID,
        request: Request,
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[CampaignCommunicationLinkResponse]:
        crm = access.crm_for(
            request,
            action="campaign.communications.link",
            campaign_id=str(campaign_id),
        )
        result = crm.campaigns.communication_links(
            CampaignId(campaign_id), page.to_domain()
        )
        return PageResponse[CampaignCommunicationLinkResponse].from_page(
            result, CampaignCommunicationLinkResponse.from_domain
        )

    @router.post(
        "/{campaign_id}/communication-links",
        response_model=CampaignCommunicationLinkResponse,
        status_code=status.HTTP_201_CREATED,
        responses=_MUTATION_ERRORS,
    )
    def link_communication(
        campaign_id: UUID,
        payload: CampaignCommunicationLinkRequest,
        request: Request,
    ) -> CampaignCommunicationLinkResponse:
        crm = access.crm_for(
            request,
            action="campaign.communications.link",
            campaign_id=str(campaign_id),
        )
        linked = crm.campaigns.link_communication(
            CampaignId(campaign_id),
            CommunicationRecordId(payload.communication_id),
            role=payload.role,
            metadata=payload.metadata,
        )
        return CampaignCommunicationLinkResponse.from_domain(linked)

    @router.post(
        "/{campaign_id}/communication-links/remove",
        response_model=dict[str, bool],
        responses=_MUTATION_ERRORS,
    )
    def unlink_communication(
        campaign_id: UUID,
        payload: CampaignCommunicationUnlinkRequest,
        request: Request,
    ) -> dict[str, bool]:
        crm = access.crm_for(
            request,
            action="campaign.communications.link",
            campaign_id=str(campaign_id),
        )
        return {
            "removed": crm.campaigns.unlink_communication(
                CampaignId(campaign_id),
                CommunicationRecordId(payload.communication_id),
            )
        }

    return router


__all__ = ["create_campaign_linkage_router"]
