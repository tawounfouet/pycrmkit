"""Facade-backed DRF ViewSets for Segments and Saved Queries."""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from pycrmkit.core.ids import EntityId
from pycrmkit.integrations.django.drf.pagination import (
    PaginationQuerySerializer,
    page_payload,
)
from pycrmkit.integrations.django.drf.segmentation_serializers import (
    EntityReferenceSerializer,
    SavedQueryCreateSerializer,
    SavedQueryFilterSerializer,
    SavedQueryResponseSerializer,
    SavedQueryUpdateSerializer,
    SegmentCreateSerializer,
    SegmentFilterSerializer,
    SegmentMembersSerializer,
    SegmentResponseSerializer,
    SegmentSnapshotCreateSerializer,
    SegmentSnapshotSerializer,
    saved_query_payload,
    segment_payload,
)
from pycrmkit.integrations.django.drf.views import CRMViewSet
from pycrmkit.saved_queries import (
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryStatus,
    SavedQueryVisibility,
)
from pycrmkit.segments import (
    NullOrder,
    SegmentId,
    SegmentMode,
    SegmentQuery,
    SegmentStatus,
    SortDirection,
    SortExpression,
    expression_from_dict,
)


def _uuid_pk(value: str | None) -> UUID:
    if value is None:
        raise DRFValidationError({"id": ["resource id is required"]})
    try:
        return UUID(value)
    except ValueError as exc:
        raise DRFValidationError({"id": ["must be a valid UUID"]}) from exc


def _validated(serializer: Any) -> dict[str, Any]:
    return cast(dict[str, Any], serializer.validated_data)


def _reference_payload(reference: Any) -> dict[str, Any]:
    return {"kind": reference.kind, "id": reference.id.value}


class SegmentViewSet(CRMViewSet):
    """HTTP surface over the public Segments facade namespace."""

    def list(self, request: Request) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        filters = SegmentFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = _validated(filters)
        owner_id = data.get("owner_id")
        result = self.get_crm(request).segments.list(
            SegmentQuery(
                status=(
                    SegmentStatus(cast(str, data["status"]))
                    if "status" in data
                    else None
                ),
                mode=(
                    SegmentMode(cast(str, data["mode"]))
                    if "mode" in data
                    else None
                ),
                entity_kind=cast(str | None, data.get("entity_kind")),
                owner_id=(
                    EntityId(owner_id)
                    if owner_id is not None
                    else None
                ),
                include_archived=cast(
                    bool,
                    data.get("include_archived", False),
                ),
            ),
            pagination.to_domain(),
        )
        items = [
            dict(SegmentResponseSerializer(segment_payload(item)).data)
            for item in result.items
        ]
        return Response(page_payload(result, items))

    def create(self, request: Request) -> Response:
        serializer = SegmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        owner_id = data.get("owner_id")
        raw_expression = data.get("expression")
        segment = self.get_crm(request).segments.create(
            key=cast(str, data["key"]),
            name=cast(str, data["name"]),
            entity_kind=cast(str, data["entity_kind"]),
            mode=SegmentMode(cast(str, data["mode"])),
            description=cast(str | None, data.get("description")),
            query=(
                expression_from_dict(
                    cast(dict[str, Any], raw_expression)
                )
                if raw_expression is not None
                else None
            ),
            owner_id=(
                EntityId(owner_id)
                if owner_id is not None
                else None
            ),
            metadata=cast(
                dict[str, object],
                dict(cast(dict[str, Any], data.get("metadata", {}))),
            ),
        )
        return Response(
            SegmentResponseSerializer(segment_payload(segment)).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        segment = self.get_crm(request).segments.get(
            SegmentId(_uuid_pk(pk))
        )
        return Response(
            SegmentResponseSerializer(segment_payload(segment)).data
        )

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        segment = self.get_crm(request).segments.archive(
            SegmentId(_uuid_pk(pk))
        )
        return Response(
            SegmentResponseSerializer(segment_payload(segment)).data
        )

    @action(detail=False, methods=["post"], url_path="snapshots")
    def snapshots(self, request: Request) -> Response:
        serializer = SegmentSnapshotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        owner_id = data.get("owner_id")
        segment = self.get_crm(request).segments.create_snapshot(
            key=cast(str, data["key"]),
            name=cast(str, data["name"]),
            entity_kind=cast(str, data["entity_kind"]),
            expression=expression_from_dict(
                cast(dict[str, Any], data["expression"])
            ),
            description=cast(str | None, data.get("description")),
            owner_id=(
                EntityId(owner_id)
                if owner_id is not None
                else None
            ),
            metadata=cast(
                dict[str, object],
                dict(cast(dict[str, Any], data.get("metadata", {}))),
            ),
        )
        return Response(
            SegmentResponseSerializer(segment_payload(segment)).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def snapshot(self, request: Request, pk: str | None = None) -> Response:
        serializer = SegmentSnapshotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        owner_id = data.get("owner_id")
        segment = self.get_crm(request).segments.snapshot(
            SegmentId(_uuid_pk(pk)),
            key=cast(str, data["key"]),
            name=cast(str, data["name"]),
            description=cast(str | None, data.get("description")),
            owner_id=(
                EntityId(owner_id)
                if owner_id is not None
                else None
            ),
            metadata=cast(
                dict[str, object],
                dict(cast(dict[str, Any], data.get("metadata", {}))),
            ),
        )
        return Response(
            SegmentResponseSerializer(segment_payload(segment)).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"])
    def members(self, request: Request, pk: str | None = None) -> Response:
        segment_id = SegmentId(_uuid_pk(pk))
        if request.method == "GET":
            pagination = PaginationQuerySerializer(
                data=request.query_params
            )
            pagination.is_valid(raise_exception=True)
            result = self.get_crm(request).segments.evaluate(
                segment_id,
                pagination.to_domain(),
            )
            items = [
                dict(
                    EntityReferenceSerializer(
                        _reference_payload(item)
                    ).data
                )
                for item in result.items
            ]
            return Response(page_payload(result, items))

        serializer = SegmentMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        members = self.get_crm(request).segments.add_members(
            segment_id,
            serializer.references(),
            source=cast(str, data.get("source", "api")),
            metadata=cast(
                dict[str, object],
                dict(cast(dict[str, Any], data.get("metadata", {}))),
            ),
        )
        return Response(
            [
                dict(
                    EntityReferenceSerializer(
                        _reference_payload(member.entity)
                    ).data
                )
                for member in members
            ]
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="members/remove",
    )
    def remove_members(
        self,
        request: Request,
        pk: str | None = None,
    ) -> Response:
        serializer = SegmentMembersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        removed = self.get_crm(request).segments.remove_members(
            SegmentId(_uuid_pk(pk)),
            serializer.references(),
        )
        return Response({"removed": removed})


class SavedQueryViewSet(CRMViewSet):
    """HTTP surface over the public Saved Queries facade namespace."""

    def list(self, request: Request) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        filters = SavedQueryFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = _validated(filters)
        owner_id = data.get("owner_id")
        result = self.get_crm(request).saved_queries.list(
            SavedQueryQuery(
                status=(
                    SavedQueryStatus(cast(str, data["status"]))
                    if "status" in data
                    else None
                ),
                visibility=(
                    SavedQueryVisibility(
                        cast(str, data["visibility"])
                    )
                    if "visibility" in data
                    else None
                ),
                entity_kind=cast(str | None, data.get("entity_kind")),
                owner_id=(
                    EntityId(owner_id)
                    if owner_id is not None
                    else None
                ),
                include_archived=cast(
                    bool,
                    data.get("include_archived", False),
                ),
            ),
            pagination.to_domain(),
        )
        items = [
            dict(
                SavedQueryResponseSerializer(
                    saved_query_payload(item)
                ).data
            )
            for item in result.items
        ]
        return Response(page_payload(result, items))

    def create(self, request: Request) -> Response:
        serializer = SavedQueryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        owner_id = data.get("owner_id")
        query = self.get_crm(request).saved_queries.create(
            key=cast(str, data["key"]),
            name=cast(str, data["name"]),
            entity_kind=cast(str, data["entity_kind"]),
            expression=expression_from_dict(
                cast(dict[str, Any], data["expression"])
            ),
            ordering=tuple(
                _sort_expression(cast(dict[str, Any], item))
                for item in cast(list[Any], data.get("ordering", []))
            ),
            owner_id=(
                EntityId(owner_id)
                if owner_id is not None
                else None
            ),
            visibility=SavedQueryVisibility(
                cast(str, data["visibility"])
            ),
            metadata=cast(
                dict[str, object],
                dict(cast(dict[str, Any], data.get("metadata", {}))),
            ),
        )
        return Response(
            SavedQueryResponseSerializer(
                saved_query_payload(query)
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request: Request, pk: str | None = None) -> Response:
        revision = request.query_params.get("revision")
        parsed_revision = int(revision) if revision is not None else None
        query = self.get_crm(request).saved_queries.get(
            SavedQueryId(_uuid_pk(pk)),
            revision=parsed_revision,
        )
        return Response(
            SavedQueryResponseSerializer(
                saved_query_payload(query)
            ).data
        )

    def partial_update(
        self,
        request: Request,
        pk: str | None = None,
    ) -> Response:
        serializer = SavedQueryUpdateSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        data = _validated(serializer)
        query = self.get_crm(request).saved_queries.update(
            SavedQueryId(_uuid_pk(pk)),
            serializer.to_domain(),
            expected_revision=cast(
                int | None,
                data.get("expected_revision"),
            ),
        )
        return Response(
            SavedQueryResponseSerializer(
                saved_query_payload(query)
            ).data
        )

    @action(detail=True, methods=["post"])
    def archive(self, request: Request, pk: str | None = None) -> Response:
        raw = request.data.get("expected_revision")
        expected = int(raw) if raw is not None else None
        query = self.get_crm(request).saved_queries.archive(
            SavedQueryId(_uuid_pk(pk)),
            expected_revision=expected,
        )
        return Response(
            SavedQueryResponseSerializer(
                saved_query_payload(query)
            ).data
        )

    @action(detail=True, methods=["get"])
    def revisions(self, request: Request, pk: str | None = None) -> Response:
        values = self.get_crm(request).saved_queries.revisions(
            SavedQueryId(_uuid_pk(pk))
        )
        return Response(
            [
                dict(
                    SavedQueryResponseSerializer(
                        saved_query_payload(item)
                    ).data
                )
                for item in values
            ]
        )

    @action(detail=True, methods=["get"])
    def execute(self, request: Request, pk: str | None = None) -> Response:
        pagination = PaginationQuerySerializer(data=request.query_params)
        pagination.is_valid(raise_exception=True)
        raw_revision = request.query_params.get("revision")
        revision = (
            int(raw_revision)
            if raw_revision is not None
            else None
        )
        result = self.get_crm(request).saved_queries.execute(
            SavedQueryId(_uuid_pk(pk)),
            pagination.to_domain(),
            revision=revision,
        )
        items = [
            dict(
                EntityReferenceSerializer(
                    _reference_payload(item)
                ).data
            )
            for item in result.items
        ]
        return Response(page_payload(result, items))


def _sort_expression(data: dict[str, Any]) -> SortExpression:
    return SortExpression(
        cast(str, data["field"]),
        SortDirection(cast(str, data["direction"])),
        NullOrder(cast(str, data["null_order"])),
    )


__all__ = ["SavedQueryViewSet", "SegmentViewSet"]
