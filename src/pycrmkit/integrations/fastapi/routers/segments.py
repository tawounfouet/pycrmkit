"""FastAPI router for Segments."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from pycrmkit import CRM
from pycrmkit.core.ids import EntityId
from pycrmkit.core.references import EntityReference
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
    SegmentCreateRequest,
    SegmentMembersRequest,
    SegmentResponse,
    SegmentSnapshotCreateRequest,
    SegmentSnapshotRequest,
)
from pycrmkit.segments import (
    SegmentId,
    SegmentMode,
    SegmentQuery,
    SegmentStatus,
    expression_from_dict,
)


def _members(request: SegmentMembersRequest) -> tuple[EntityReference, ...]:
    return tuple(item.to_domain() for item in request.members)


def create_segments_router(dependency: CRMDependency) -> APIRouter:
    """Build the Segments router against one request-scoped CRM dependency."""

    router = APIRouter(prefix="/segments", tags=["segments"])

    @router.post(
        "",
        response_model=SegmentResponse,
        status_code=status.HTTP_201_CREATED,
        responses=CREATE_ERROR_RESPONSES,
    )
    def create_segment(
        request: SegmentCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SegmentResponse:
        segment = crm.segments.create(
            key=request.key,
            name=request.name,
            entity_kind=request.entity_kind,
            mode=request.mode,
            description=request.description,
            query=request.expression_domain(),
            owner_id=(
                EntityId(request.owner_id)
                if request.owner_id is not None
                else None
            ),
            metadata=request.metadata,
        )
        return SegmentResponse.from_domain(segment)

    @router.post(
        "/snapshots",
        response_model=SegmentResponse,
        status_code=status.HTTP_201_CREATED,
        responses=CREATE_ERROR_RESPONSES,
    )
    def create_snapshot(
        request: SegmentSnapshotCreateRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SegmentResponse:
        segment = crm.segments.create_snapshot(
            key=request.key,
            name=request.name,
            entity_kind=request.entity_kind,
            expression=expression_from_dict(dict(request.expression)),
            description=request.description,
            owner_id=(
                EntityId(request.owner_id)
                if request.owner_id is not None
                else None
            ),
            metadata=request.metadata,
        )
        return SegmentResponse.from_domain(segment)

    @router.get(
        "",
        response_model=PageResponse[SegmentResponse],
        responses=LIST_ERROR_RESPONSES,
    )
    def list_segments(
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
        status_filter: SegmentStatus | None = None,
        mode: SegmentMode | None = None,
        entity_kind: str | None = None,
        owner_id: UUID | None = None,
        include_archived: bool = False,
    ) -> PageResponse[SegmentResponse]:
        result = crm.segments.list(
            SegmentQuery(
                status=status_filter,
                mode=mode,
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
        return PageResponse[SegmentResponse].from_page(
            result,
            SegmentResponse.from_domain,
        )

    @router.get(
        "/{segment_id}",
        response_model=SegmentResponse,
        responses=READ_ERROR_RESPONSES,
    )
    def get_segment(
        segment_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SegmentResponse:
        return SegmentResponse.from_domain(
            crm.segments.get(SegmentId(segment_id))
        )

    @router.post(
        "/{segment_id}/archive",
        response_model=SegmentResponse,
        responses=MUTATION_ERROR_RESPONSES,
    )
    def archive_segment(
        segment_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SegmentResponse:
        return SegmentResponse.from_domain(
            crm.segments.archive(SegmentId(segment_id))
        )

    @router.get(
        "/{segment_id}/members",
        response_model=PageResponse[EntityReferenceSchema],
        responses=LIST_ERROR_RESPONSES,
    )
    def list_segment_members(
        segment_id: UUID,
        crm: Annotated[CRM, Depends(dependency)],
        page: Annotated[PaginationParams, Depends(pagination_params)],
    ) -> PageResponse[EntityReferenceSchema]:
        result = crm.segments.evaluate(
            SegmentId(segment_id),
            page.to_domain(),
        )
        return PageResponse[EntityReferenceSchema].from_page(
            result,
            EntityReferenceSchema.from_domain,
        )

    @router.post(
        "/{segment_id}/members",
        response_model=list[EntityReferenceSchema],
        responses=MUTATION_ERROR_RESPONSES,
    )
    def add_segment_members(
        segment_id: UUID,
        request: SegmentMembersRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> list[EntityReferenceSchema]:
        members = crm.segments.add_members(
            SegmentId(segment_id),
            _members(request),
            source=request.source,
            metadata=request.metadata,
        )
        return [
            EntityReferenceSchema.from_domain(member.entity)
            for member in members
        ]

    @router.post(
        "/{segment_id}/members/remove",
        responses=MUTATION_ERROR_RESPONSES,
    )
    def remove_segment_members(
        segment_id: UUID,
        request: SegmentMembersRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> dict[str, int]:
        removed = crm.segments.remove_members(
            SegmentId(segment_id),
            _members(request),
        )
        return {"removed": removed}

    @router.post(
        "/{segment_id}/snapshot",
        response_model=SegmentResponse,
        status_code=status.HTTP_201_CREATED,
        responses=MUTATION_ERROR_RESPONSES,
    )
    def snapshot_segment(
        segment_id: UUID,
        request: SegmentSnapshotRequest,
        crm: Annotated[CRM, Depends(dependency)],
    ) -> SegmentResponse:
        segment = crm.segments.snapshot(
            SegmentId(segment_id),
            key=request.key,
            name=request.name,
            description=request.description,
            owner_id=(
                EntityId(request.owner_id)
                if request.owner_id is not None
                else None
            ),
            metadata=request.metadata,
        )
        return SegmentResponse.from_domain(segment)

    return router


__all__ = ["create_segments_router"]
