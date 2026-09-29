"""Explicit Domain <-> SQLAlchemy mappings for Segmentation."""

from __future__ import annotations

from datetime import UTC, datetime

from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.references import EntityReference
from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryStatus,
    SavedQueryVisibility,
)
from pycrmkit.segments import (
    NullOrder,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentMode,
    SegmentStatus,
    SortDirection,
    SortExpression,
    expression_from_dict,
    expression_to_dict,
)
from pycrmkit.storage.sqlalchemy.models.segmentation import (
    SavedQueryModel,
    SegmentMemberModel,
    SegmentModel,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def segment_to_model(
    segment: Segment,
    model: SegmentModel | None = None,
) -> SegmentModel:
    target = model or SegmentModel(
        id=str(segment.id),
        created_at=segment.created_at,
        updated_at=segment.updated_at,
    )
    target.key = segment.key
    target.name = segment.name
    target.entity_kind = segment.entity_kind
    target.mode = segment.mode.value
    target.description = segment.description
    target.status = segment.status.value
    target.query_json = (
        expression_to_dict(segment.query)
        if segment.query is not None
        else None
    )
    target.saved_query_id = (
        str(segment.saved_query_id)
        if segment.saved_query_id is not None
        else None
    )
    target.saved_query_revision = segment.saved_query_revision
    target.owner_id = (
        str(segment.owner_id) if segment.owner_id is not None else None
    )
    target.revision = segment.revision
    target.metadata_json = dict(segment.metadata)
    target.archived_at = segment.archived_at
    target.created_at = segment.created_at
    target.updated_at = segment.updated_at
    return target


def segment_from_model(model: SegmentModel) -> Segment:
    return Segment(
        id=SegmentId.parse(model.id),
        created_at=_required_aware(model.created_at),
        updated_at=_required_aware(model.updated_at),
        key=model.key,
        name=model.name,
        entity_kind=model.entity_kind,
        mode=SegmentMode(model.mode),
        description=model.description,
        status=SegmentStatus(model.status),
        query=(
            expression_from_dict(model.query_json)
            if model.query_json is not None
            else None
        ),
        saved_query_id=(
            UUIDId.parse(model.saved_query_id)
            if model.saved_query_id is not None
            else None
        ),
        saved_query_revision=model.saved_query_revision,
        owner_id=(
            EntityId.parse(model.owner_id)
            if model.owner_id is not None
            else None
        ),
        revision=model.revision,
        metadata=dict(model.metadata_json or {}),
        archived_at=_aware(model.archived_at),
    )


def segment_member_to_model(member: SegmentMember) -> SegmentMemberModel:
    return SegmentMemberModel(
        segment_id=str(member.segment_id),
        entity_kind=member.entity.kind,
        entity_id=str(member.entity.id),
        added_at=member.added_at,
        source=member.source,
        actor_id=member.actor_id,
        metadata_json=dict(member.metadata),
    )


def segment_member_from_model(model: SegmentMemberModel) -> SegmentMember:
    return SegmentMember(
        segment_id=SegmentId.parse(model.segment_id),
        entity=EntityReference(
            model.entity_kind,
            UUIDId.parse(model.entity_id),
        ),
        added_at=_required_aware(model.added_at),
        source=model.source,
        actor_id=model.actor_id,
        metadata=dict(model.metadata_json or {}),
    )


def saved_query_to_model(query: SavedQuery) -> SavedQueryModel:
    return SavedQueryModel(
        id=str(query.id),
        revision=query.revision,
        key=query.key,
        name=query.name,
        entity_kind=query.entity_kind,
        expression_json=expression_to_dict(query.expression),
        ordering_json=[
            {
                "field": item.field,
                "direction": item.direction.value,
                "null_order": item.null_order.value,
            }
            for item in query.ordering
        ],
        owner_id=(
            str(query.owner_id) if query.owner_id is not None else None
        ),
        visibility=query.visibility.value,
        status=query.status.value,
        metadata_json=dict(query.metadata),
        archived_at=query.archived_at,
        created_at=query.created_at,
        updated_at=query.updated_at,
    )


def saved_query_from_model(model: SavedQueryModel) -> SavedQuery:
    return SavedQuery(
        id=SavedQueryId.parse(model.id),
        created_at=_required_aware(model.created_at),
        updated_at=_required_aware(model.updated_at),
        key=model.key,
        name=model.name,
        entity_kind=model.entity_kind,
        expression=expression_from_dict(model.expression_json),
        ordering=tuple(
            SortExpression(
                field=item["field"],
                direction=SortDirection(item.get("direction", "asc")),
                null_order=NullOrder(item.get("null_order", "last")),
            )
            for item in (model.ordering_json or [])
        ),
        owner_id=(
            EntityId.parse(model.owner_id)
            if model.owner_id is not None
            else None
        ),
        visibility=SavedQueryVisibility(model.visibility),
        status=SavedQueryStatus(model.status),
        revision=model.revision,
        metadata=dict(model.metadata_json or {}),
        archived_at=_aware(model.archived_at),
    )


def _required_aware(value: datetime) -> datetime:
    normalized = _aware(value)
    assert normalized is not None
    return normalized


__all__ = [
    "saved_query_from_model",
    "saved_query_to_model",
    "segment_from_model",
    "segment_member_from_model",
    "segment_member_to_model",
    "segment_to_model",
]
