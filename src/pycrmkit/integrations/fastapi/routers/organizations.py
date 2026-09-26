"""FastAPI router for the public Organizations facade."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.integrations.fastapi.dependencies import CRMDependency
from pycrmkit.integrations.fastapi.errors import (
    CREATE_ERROR_RESPONSES,
    LIST_ERROR_RESPONSES,
    MUTATION_ERROR_RESPONSES,
    READ_ERROR_RESPONSES,
)
from pycrmkit.integrations.fastapi.pagination import (
    PageResponse,
    PaginationParams,
    pagination_params,
)
from pycrmkit.integrations.fastapi.schemas import (
    OrganizationCreateRequest,
    OrganizationResponse,
    OrganizationUpdateRequest,
)
from pycrmkit.organizations import OrganizationId


def create_organizations_router(dependency: CRMDependency) -> APIRouter:
    """Build the Organizations router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/organizations", tags=["organizations"])

    @router.post(
        "",
        response_model=OrganizationResponse,
        status_code=status.HTTP_201_CREATED,
        responses=CREATE_ERROR_RESPONSES,
    )
    def create_organization(
        request: OrganizationCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OrganizationResponse:
        organization = crm.organizations.create(**request.to_domain_kwargs())
        return OrganizationResponse.from_domain(organization)

    @router.get("", response_model=PageResponse[OrganizationResponse], responses=LIST_ERROR_RESPONSES)
    def list_organizations(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[OrganizationResponse]:
        result = crm.organizations.search(page=page.to_domain())
        return PageResponse[OrganizationResponse].from_page(
            result,
            OrganizationResponse.from_domain,
        )

    @router.get("/{organization_id}", response_model=OrganizationResponse, responses=READ_ERROR_RESPONSES)
    def get_organization(
        organization_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OrganizationResponse:
        organization = crm.organizations.get(OrganizationId(organization_id))
        return OrganizationResponse.from_domain(organization)

    @router.patch("/{organization_id}", response_model=OrganizationResponse, responses=MUTATION_ERROR_RESPONSES)
    def update_organization(
        organization_id: UUID,
        request: OrganizationUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OrganizationResponse:
        organization = crm.organizations.update(
            OrganizationId(organization_id),
            request.to_domain(),
        )
        return OrganizationResponse.from_domain(organization)

    @router.post("/{organization_id}/archive", response_model=OrganizationResponse, responses=MUTATION_ERROR_RESPONSES)
    def archive_organization(
        organization_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> OrganizationResponse:
        organization = crm.organizations.archive(OrganizationId(organization_id))
        return OrganizationResponse.from_domain(organization)

    return router


__all__ = ["create_organizations_router"]
