"""FastAPI router for Saved Queries."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.core.ids import EntityId
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
from pycrmkit.integrations.fastapi.schemas import EntityReferenceSchema
from pycrmkit.integrations.fastapi.segmentation_schemas import (
    SavedQueryCreateRequest,
    SavedQueryResponse,
    SavedQueryUpdateRequest,
)
from pycrmkit.saved_queries import (
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryStatus,
    SavedQueryVisibility,
)
from pycrmkit.segments import expression_from_dict


def create_saved_queries_router(dependency: CRMDependency) -> APIRouter:
    """Build the Saved Queries router against the CRM facade."""

    router = APIRouter(prefix="/saved-queries", tags=["saved-queries"])

    @router.post(
        "",
        response_model=SavedQueryResponse,
        status_code=status.HTTP_201_CREATED,
        responses=CREATE_ERROR_RESPONSES,
    )
    def create_saved_query(
        request: SavedQueryCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SavedQueryResponse:
        query = crm.saved_queries.create(
            key=request.key,
            name=request.name,
            entity_kind=request.entity_kind,
            expression=expression_from_dict(dict(request.expression)),
            ordering=tuple(
                item.to_domain()
                for item in request.ordering
            ),
            owner_id=(
                EntityId(request.owner_id)
                if request.owner_id is not None
                else None
            ),
            visibility=request.visibility,
            metadata=request.metadata,
        )
        return SavedQueryResponse.from_domain(query)

    @router.get(
        "",
        response_model=PageResponse[SavedQueryResponse],
        responses=LIST_ERROR_RESPONSES,
    )
    def list_saved_queries(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
        status_filter: SavedQueryStatus | None = None,
        visibility: SavedQueryVisibility | None = None,
        entity_kind: str | None = None,
        owner_id: UUID | None = None,
        include_archived: bool = False,
    ) -> PageResponse[SavedQueryResponse]:
        result = crm.saved_queries.list(
            SavedQueryQuery(
                status=status_filter,
                visibility=visibility,
                entity_kind=entity_kind,
                owner_id=(
                    EntityId(owner_id)
                    if owner_id is not None
                    else None
                ),
                include_archived=include_archived,
            ),
            page.to_domain(),
        )
        return PageResponse[SavedQueryResponse].from_page(
            result,
            SavedQueryResponse.from_domain,
        )

    @router.get(
        "/{query_id}",
        response_model=SavedQueryResponse,
        responses=READ_ERROR_RESPONSES,
    )
    def get_saved_query(
        query_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        revision: int | None = None,
    ) -> SavedQueryResponse:
        return SavedQueryResponse.from_domain(
            crm.saved_queries.get(
                SavedQueryId(query_id),
                revision=revision,
            )
        )

    @router.patch(
        "/{query_id}",
        response_model=SavedQueryResponse,
        responses=MUTATION_ERROR_RESPONSES,
    )
    def update_saved_query(
        query_id: UUID,
        request: SavedQueryUpdateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SavedQueryResponse:
        query = crm.saved_queries.update(
            SavedQueryId(query_id),
            request.to_domain(),
            expected_revision=request.expected_revision,
        )
        return SavedQueryResponse.from_domain(query)

    @router.post(
        "/{query_id}/archive",
        response_model=SavedQueryResponse,
        responses=MUTATION_ERROR_RESPONSES,
    )
    def archive_saved_query(
        query_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        expected_revision: int | None = None,
    ) -> SavedQueryResponse:
        query = crm.saved_queries.archive(
            SavedQueryId(query_id),
            expected_revision=expected_revision,
        )
        return SavedQueryResponse.from_domain(query)

    @router.get(
        "/{query_id}/revisions",
        response_model=list[SavedQueryResponse],
        responses=READ_ERROR_RESPONSES,
    )
    def list_saved_query_revisions(
        query_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> list[SavedQueryResponse]:
        return [
            SavedQueryResponse.from_domain(item)
            for item in crm.saved_queries.revisions(
                SavedQueryId(query_id)
            )
        ]

    @router.get(
        "/{query_id}/execute",
        response_model=PageResponse[EntityReferenceSchema],
        responses=LIST_ERROR_RESPONSES,
    )
    def execute_saved_query(
        query_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
        revision: int | None = None,
    ) -> PageResponse[EntityReferenceSchema]:
        result = crm.saved_queries.execute(
            SavedQueryId(query_id),
            page.to_domain(),
            revision=revision,
        )
        return PageResponse[EntityReferenceSchema].from_page(
            result,
            EntityReferenceSchema.from_domain,
        )

    return router


__all__ = ["create_saved_queries_router"]
