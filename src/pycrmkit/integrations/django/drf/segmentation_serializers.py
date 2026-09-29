"""DRF serializers for Segments and Saved Queries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from rest_framework import serializers

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference, normalize_entity_kind
from pycrmkit.leads import LeadId
from pycrmkit.opportunities import OpportunityId
from pycrmkit.organizations import OrganizationId
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

if TYPE_CHECKING:
    class _SerializerBase(serializers.Serializer[Any]):
        pass
else:
    _SerializerBase = serializers.Serializer


def _data(serializer: serializers.Serializer[Any]) -> dict[str, Any]:
    return cast(dict[str, Any], serializer.validated_data)


def _entity_reference(data: dict[str, Any]) -> EntityReference:
    kind = normalize_entity_kind(cast(str, data["kind"]))
    raw = data["id"]
    identifier = str(raw)
    id_type: type[UUIDId] = {
        "contact": ContactId,
        "organization": OrganizationId,
        "lead": LeadId,
        "opportunity": OpportunityId,
    }.get(kind, UUIDId)
    return EntityReference(kind, id_type.parse(identifier))


class EntityReferenceSerializer(_SerializerBase):
    kind = serializers.CharField(max_length=64)
    id = serializers.UUIDField()


class SortExpressionSerializer(_SerializerBase):
    field = serializers.CharField(max_length=129)
    direction = serializers.ChoiceField(
        choices=[item.value for item in SortDirection],
        required=False,
        default=SortDirection.ASC.value,
    )
    null_order = serializers.ChoiceField(
        choices=[item.value for item in NullOrder],
        required=False,
        default=NullOrder.LAST.value,
    )

    def to_domain(self) -> SortExpression:
        data = _data(self)
        return SortExpression(
            cast(str, data["field"]),
            SortDirection(cast(str, data["direction"])),
            NullOrder(cast(str, data["null_order"])),
        )


class SegmentFilterSerializer(_SerializerBase):
    status = serializers.ChoiceField(
        choices=[item.value for item in SegmentStatus],
        required=False,
    )
    mode = serializers.ChoiceField(
        choices=[item.value for item in SegmentMode],
        required=False,
    )
    entity_kind = serializers.CharField(max_length=64, required=False)
    owner_id = serializers.UUIDField(required=False)
    include_archived = serializers.BooleanField(required=False, default=False)


class SegmentCreateSerializer(_SerializerBase):
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    entity_kind = serializers.CharField(max_length=64)
    mode = serializers.ChoiceField(
        choices=[item.value for item in SegmentMode]
    )
    description = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    expression = serializers.JSONField(required=False, allow_null=True)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class SegmentSnapshotCreateSerializer(_SerializerBase):
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    entity_kind = serializers.CharField(max_length=64)
    expression = serializers.JSONField()
    description = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class SegmentSnapshotSerializer(_SerializerBase):
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(
        max_length=2000,
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False, default=dict)


class SegmentMembersSerializer(_SerializerBase):
    members = EntityReferenceSerializer(many=True)
    source = serializers.CharField(
        max_length=120,
        required=False,
        default="api",
    )
    metadata = serializers.JSONField(required=False, default=dict)

    def validate_members(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not value:
            raise serializers.ValidationError("at least one member is required")
        if len(value) > 1000:
            raise serializers.ValidationError("at most 1000 members are allowed")
        return value

    def references(self) -> tuple[EntityReference, ...]:
        return tuple(
            _entity_reference(cast(dict[str, Any], item))
            for item in cast(list[Any], _data(self)["members"])
        )


class SegmentResponseSerializer(_SerializerBase):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    key = serializers.CharField()
    name = serializers.CharField()
    entity_kind = serializers.CharField()
    mode = serializers.ChoiceField(choices=[item.value for item in SegmentMode])
    description = serializers.CharField(allow_null=True)
    status = serializers.ChoiceField(choices=[item.value for item in SegmentStatus])
    expression = serializers.JSONField(allow_null=True)
    saved_query_id = serializers.UUIDField(allow_null=True)
    saved_query_revision = serializers.IntegerField(allow_null=True)
    owner_id = serializers.UUIDField(allow_null=True)
    revision = serializers.IntegerField()
    metadata = serializers.JSONField()
    archived_at = serializers.DateTimeField(allow_null=True)


class SavedQueryFilterSerializer(_SerializerBase):
    status = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryStatus],
        required=False,
    )
    visibility = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryVisibility],
        required=False,
    )
    entity_kind = serializers.CharField(max_length=64, required=False)
    owner_id = serializers.UUIDField(required=False)
    include_archived = serializers.BooleanField(required=False, default=False)


class SavedQueryCreateSerializer(_SerializerBase):
    key = serializers.CharField(max_length=120)
    name = serializers.CharField(max_length=200)
    entity_kind = serializers.CharField(max_length=64)
    expression = serializers.JSONField()
    ordering = SortExpressionSerializer(many=True, required=False, default=list)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    visibility = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryVisibility],
        required=False,
        default=SavedQueryVisibility.PRIVATE.value,
    )
    metadata = serializers.JSONField(required=False, default=dict)


class SavedQueryUpdateSerializer(_SerializerBase):
    name = serializers.CharField(max_length=200, required=False)
    expression = serializers.JSONField(required=False)
    ordering = SortExpressionSerializer(many=True, required=False)
    owner_id = serializers.UUIDField(required=False, allow_null=True)
    visibility = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryVisibility],
        required=False,
    )
    metadata = serializers.JSONField(required=False)
    expected_revision = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
    )

    def to_domain(self) -> SavedQueryRevision:
        data = _data(self)
        owner_id = data.get("owner_id")
        return SavedQueryRevision(
            name=cast(str, data["name"]) if "name" in data else UNSET,
            expression=(
                expression_from_dict(
                    cast(dict[str, Any], data["expression"])
                )
                if "expression" in data
                else UNSET
            ),
            ordering=(
                tuple(
                    SortExpression(
                        cast(str, cast(dict[str, Any], item)["field"]),
                        SortDirection(
                            cast(str, cast(dict[str, Any], item)["direction"])
                        ),
                        NullOrder(
                            cast(str, cast(dict[str, Any], item)["null_order"])
                        ),
                    )
                    for item in cast(list[Any], data["ordering"])
                )
                if "ordering" in data
                else UNSET
            ),
            owner_id=(
                EntityId(owner_id)
                if owner_id is not None
                else None
            )
            if "owner_id" in data
            else UNSET,
            visibility=(
                SavedQueryVisibility(cast(str, data["visibility"]))
                if "visibility" in data
                else UNSET
            ),
            metadata=(
                cast(dict[str, object], dict(cast(dict[str, Any], data["metadata"])))
                if "metadata" in data
                else UNSET
            ),
        )


class SavedQueryResponseSerializer(_SerializerBase):
    id = serializers.UUIDField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    key = serializers.CharField()
    name = serializers.CharField()
    entity_kind = serializers.CharField()
    expression = serializers.JSONField()
    ordering = SortExpressionSerializer(many=True)
    owner_id = serializers.UUIDField(allow_null=True)
    visibility = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryVisibility]
    )
    status = serializers.ChoiceField(
        choices=[item.value for item in SavedQueryStatus]
    )
    revision = serializers.IntegerField()
    metadata = serializers.JSONField()
    archived_at = serializers.DateTimeField(allow_null=True)


def segment_payload(value: Segment) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "key": value.key,
        "name": value.name,
        "entity_kind": value.entity_kind,
        "mode": value.mode.value,
        "description": value.description,
        "status": value.status.value,
        "expression": (
            expression_to_dict(value.query)
            if value.query is not None
            else None
        ),
        "saved_query_id": (
            value.saved_query_id.value
            if value.saved_query_id is not None
            else None
        ),
        "saved_query_revision": value.saved_query_revision,
        "owner_id": (
            value.owner_id.value
            if value.owner_id is not None
            else None
        ),
        "revision": value.revision,
        "metadata": dict(value.metadata),
        "archived_at": value.archived_at,
    }


def saved_query_payload(value: SavedQuery) -> dict[str, Any]:
    return {
        "id": value.id.value,
        "created_at": value.created_at,
        "updated_at": value.updated_at,
        "key": value.key,
        "name": value.name,
        "entity_kind": value.entity_kind,
        "expression": expression_to_dict(value.expression),
        "ordering": [
            {
                "field": item.field,
                "direction": item.direction.value,
                "null_order": item.null_order.value,
            }
            for item in value.ordering
        ],
        "owner_id": (
            value.owner_id.value
            if value.owner_id is not None
            else None
        ),
        "visibility": value.visibility.value,
        "status": value.status.value,
        "revision": value.revision,
        "metadata": dict(value.metadata),
        "archived_at": value.archived_at,
    }


__all__ = [
    "EntityReferenceSerializer",
    "SavedQueryCreateSerializer",
    "SavedQueryFilterSerializer",
    "SavedQueryResponseSerializer",
    "SavedQueryUpdateSerializer",
    "SegmentCreateSerializer",
    "SegmentFilterSerializer",
    "SegmentMembersSerializer",
    "SegmentResponseSerializer",
    "SegmentSnapshotCreateSerializer",
    "SegmentSnapshotSerializer",
    "SortExpressionSerializer",
    "saved_query_payload",
    "segment_payload",
]
