"""FastAPI router for the public Relationships facade."""

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
    RelationshipCreateRequest,
    RelationshipResponse,
    RelationshipUpdateRequest,
)
from pycrmkit.relationships import RelationshipId


def create_relationships_router(dependency: CRMDependency) -> APIRouter:
    """Build the Relationships router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/relationships", tags=["relationships"])

    @router.post(
        "",
        response_model=RelationshipResponse,
        status_code=status.HTTP_201_CREATED,
        responses=CREATE_ERROR_RESPONSES,
    )
    def create_relationship(
        request: RelationshipCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> RelationshipResponse:
        relationship = crm.relationships.create(**request.to_domain_kwargs())
        return RelationshipResponse.from_domain(relationship)

    @router.get("", response_model=PageResponse[RelationshipResponse], responses=LIST_ERROR_RESPONSES)
    def list_relationships(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[RelationshipResponse]:
        result = crm.relationships.search(page=page.to_domain())
        return PageResponse[RelationshipResponse].from_page(
            result,
            RelationshipResponse.from_domain,
        )

    @router.get("/{relationship_id}", response_model=RelationshipResponse, responses=READ_ERROR_RESPONSES)
    def get_relationship(
        relationship_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> RelationshipResponse:
        relationship = crm.relationships.get(RelationshipId(relationship_id))
        return RelationshipResponse.from_domain(relationship)

    @router.patch("/{relationship_id}", response_model=RelationshipResponse, responses=MUTATION_ERROR_RESPONSES)
    def update_relationship(
        relationship_id: UUID,
        request: RelationshipUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> RelationshipResponse:
        relationship = crm.relationships.update(
            RelationshipId(relationship_id),
            request.to_domain(),
        )
        return RelationshipResponse.from_domain(relationship)

    @router.post("/{relationship_id}/end", response_model=RelationshipResponse, responses=MUTATION_ERROR_RESPONSES)
    def end_relationship(
        relationship_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> RelationshipResponse:
        relationship = crm.relationships.end(RelationshipId(relationship_id))
        return RelationshipResponse.from_domain(relationship)

    return router


__all__ = ["create_relationships_router"]
