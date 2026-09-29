"""Transport schemas for Segments and Saved Queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pycrmkit.core.ids import EntityId
from pycrmkit.saved_queries import (
    UNSET,
    SavedQuery,
    SavedQueryRevision,
    SavedQueryStatus,
    SavedQueryVisibility,
)
from pycrmkit.segments import (
    NullOrder,
    Segment,
    SegmentMode,
    SegmentStatus,
    SortDirection,
    SortExpression,
    expression_from_dict,
    expression_to_dict,
)


class SegmentationAPIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SortExpressionSchema(SegmentationAPIModel):
    field: str
    direction: SortDirection = SortDirection.ASC
    null_order: NullOrder = NullOrder.LAST

    def to_domain(self) -> SortExpression:
        return SortExpression(
            self.field,
            self.direction,
            self.null_order,
        )

    @classmethod
    def from_domain(cls, value: SortExpression) -> SortExpressionSchema:
        return cls(
            field=value.field,
            direction=value.direction,
            null_order=value.null_order,
        )


class SegmentCreateRequest(SegmentationAPIModel):
    key: str
    name: str
    entity_kind: str
    mode: SegmentMode
    description: str | None = None
    expression: dict[str, Any] | None = None
    owner_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def expression_domain(self):
        return (
            expression_from_dict(dict(self.expression))
            if self.expression is not None
            else None
        )


class SegmentSnapshotCreateRequest(SegmentationAPIModel):
    key: str
    name: str
    entity_kind: str
    expression: dict[str, Any]
    description: str | None = None
    owner_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentSnapshotRequest(SegmentationAPIModel):
    key: str
    name: str
    description: str | None = None
    owner_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentResponse(SegmentationAPIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    key: str
    name: str
    entity_kind: str
    mode: SegmentMode
    description: str | None
    status: SegmentStatus
    expression: dict[str, Any] | None
    saved_query_id: UUID | None
    saved_query_revision: int | None
    owner_id: UUID | None
    revision: int
    metadata: dict[str, Any]
    archived_at: datetime | None

    @classmethod
    def from_domain(cls, value: Segment) -> SegmentResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            key=value.key,
            name=value.name,
            entity_kind=value.entity_kind,
            mode=value.mode,
            description=value.description,
            status=value.status,
            expression=(
                expression_to_dict(value.query)
                if value.query is not None
                else None
            ),
            saved_query_id=(
                value.saved_query_id.value
                if value.saved_query_id is not None
                else None
            ),
            saved_query_revision=value.saved_query_revision,
            owner_id=(
                value.owner_id.value
                if value.owner_id is not None
                else None
            ),
            revision=value.revision,
            metadata=dict(value.metadata),
            archived_at=value.archived_at,
        )


class SegmentMembersRequest(SegmentationAPIModel):
    members: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=1000,
    )
    source: str = "api"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SavedQueryCreateRequest(SegmentationAPIModel):
    key: str
    name: str
    entity_kind: str
    expression: dict[str, Any]
    ordering: list[SortExpressionSchema] = Field(default_factory=list)
    owner_id: UUID | None = None
    visibility: SavedQueryVisibility = SavedQueryVisibility.PRIVATE
    metadata: dict[str, Any] = Field(default_factory=dict)


class SavedQueryUpdateRequest(SegmentationAPIModel):
    name: str | None = None
    expression: dict[str, Any] | None = None
    ordering: list[SortExpressionSchema] | None = None
    owner_id: UUID | None = None
    visibility: SavedQueryVisibility | None = None
    metadata: dict[str, Any] | None = None
    expected_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _reject_null_non_nullable_fields(self) -> Self:
        for name in ("name", "expression", "ordering", "visibility", "metadata"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def to_domain(self) -> SavedQueryRevision:
        fields = self.model_fields_set
        return SavedQueryRevision(
            name=self.name if "name" in fields else UNSET,
            expression=(
                expression_from_dict(dict(self.expression or {}))
                if "expression" in fields
                else UNSET
            ),
            ordering=(
                tuple(item.to_domain() for item in (self.ordering or []))
                if "ordering" in fields
                else UNSET
            ),
            owner_id=(
                EntityId(self.owner_id)
                if self.owner_id is not None
                else None
            )
            if "owner_id" in fields
            else UNSET,
            visibility=(
                self.visibility
                if "visibility" in fields
                else UNSET
            ),
            metadata=(
                dict(self.metadata or {})
                if "metadata" in fields
                else UNSET
            ),
        )


class SavedQueryResponse(SegmentationAPIModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    key: str
    name: str
    entity_kind: str
    expression: dict[str, Any]
    ordering: list[SortExpressionSchema]
    owner_id: UUID | None
    visibility: SavedQueryVisibility
    status: SavedQueryStatus
    revision: int
    metadata: dict[str, Any]
    archived_at: datetime | None

    @classmethod
    def from_domain(cls, value: SavedQuery) -> SavedQueryResponse:
        return cls(
            id=value.id.value,
            created_at=value.created_at,
            updated_at=value.updated_at,
            key=value.key,
            name=value.name,
            entity_kind=value.entity_kind,
            expression=expression_to_dict(value.expression),
            ordering=[
                SortExpressionSchema.from_domain(item)
                for item in value.ordering
            ],
            owner_id=(
                value.owner_id.value
                if value.owner_id is not None
                else None
            ),
            visibility=value.visibility,
            status=value.status,
            revision=value.revision,
            metadata=dict(value.metadata),
            archived_at=value.archived_at,
        )


__all__ = [
    "SavedQueryCreateRequest",
    "SavedQueryResponse",
    "SavedQueryUpdateRequest",
    "SegmentCreateRequest",
    "SegmentMembersRequest",
    "SegmentResponse",
    "SegmentSnapshotCreateRequest",
    "SegmentSnapshotRequest",
    "SortExpressionSchema",
]
