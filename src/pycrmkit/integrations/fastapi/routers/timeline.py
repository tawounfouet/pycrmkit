"""FastAPI router for the public Timeline facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from pycrmkit import CRM
from pycrmkit.contacts import ContactId
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.errors import (
    LIST_ERROR_RESPONSES,
    READ_ERROR_RESPONSES,
)
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import TimelineEntryResponse
from pycrmkit.organizations import OrganizationId
from pycrmkit.timeline import TimelineEntryId


def create_timeline_router(dependency: CRMDependency) -> APIRouter:
    """Build read-only Timeline routes against the public CRM facade."""

    router = APIRouter(prefix="/timeline", tags=["timeline"])

    @router.get("/entries/{entry_id}", response_model=TimelineEntryResponse, responses=READ_ERROR_RESPONSES)
    def get_timeline_entry(
        entry_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> TimelineEntryResponse:
        entry = crm.timeline.get(TimelineEntryId(entry_id))
        return TimelineEntryResponse.from_domain(entry)

    @router.get(
        "/contacts/{contact_id}",
        response_model=PageResponse[TimelineEntryResponse],
        responses=LIST_ERROR_RESPONSES,
        responses=LIST_ERROR_RESPONSES,
    )
    def contact_timeline(
        contact_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[TimelineEntryResponse]:
        result = crm.timeline.for_contact(ContactId(contact_id), page.to_domain())
        return PageResponse[TimelineEntryResponse].from_page(
            result,
            TimelineEntryResponse.from_domain,
        )

    @router.get(
        "/organizations/{organization_id}",
        response_model=PageResponse[TimelineEntryResponse],
    )
    def organization_timeline(
        organization_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[TimelineEntryResponse]:
        result = crm.timeline.for_organization(
            OrganizationId(organization_id),
            page.to_domain(),
        )
        return PageResponse[TimelineEntryResponse].from_page(
            result,
            TimelineEntryResponse.from_domain,
        )

    return router


__all__ = ["create_timeline_router"]
