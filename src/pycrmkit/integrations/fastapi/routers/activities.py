"""FastAPI router for the public Activities facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.activities import ActivityId
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import (
    ActivityCreateRequest,
    ActivityResponse,
    ActivityUpdateRequest,
)


def create_activities_router(dependency: CRMDependency) -> APIRouter:
    """Build the Activities router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/activities", tags=["activities"])

    @router.post(
        "",
        response_model=ActivityResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_activity(
        request: ActivityCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ActivityResponse:
        activity = crm.activities.log(**request.to_domain_kwargs())
        return ActivityResponse.from_domain(activity)

    @router.get("", response_model=PageResponse[ActivityResponse])
    def list_activities(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[ActivityResponse]:
        result = crm.activities.list(page=page.to_domain())
        return PageResponse[ActivityResponse].from_page(
            result,
            ActivityResponse.from_domain,
        )

    @router.get("/{activity_id}", response_model=ActivityResponse)
    def get_activity(
        activity_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ActivityResponse:
        activity = crm.activities.get(ActivityId(activity_id))
        return ActivityResponse.from_domain(activity)

    @router.patch("/{activity_id}", response_model=ActivityResponse)
    def update_activity(
        activity_id: UUID,
        request: ActivityUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> ActivityResponse:
        activity = crm.activities.update(ActivityId(activity_id), request.to_domain())
        return ActivityResponse.from_domain(activity)

    return router


__all__ = ["create_activities_router"]
