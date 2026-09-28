"""In-memory Segmentation repositories and query evaluator."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from pycrmkit.contacts import Contact
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.exceptions import DuplicateError, NotFoundError
from pycrmkit.leads import Lead
from pycrmkit.opportunities import Opportunity
from pycrmkit.organizations import Organization
from pycrmkit.segments import (
    And,
    Not,
    Or,
    Predicate,
    QueryExpression,
    QueryOperator,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentQuery,
    SegmentStatus,
    default_query_schemas,
    normalize_segment_key,
)
from pycrmkit.segments.schema import QueryField
from pycrmkit.storage.memory._state import _MemoryState

SegmentEntity = Contact | Organization | Lead | Opportunity


class MemorySegmentRepository:
    """Copy-isolated in-memory Segment repository."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def get(self, segment_id: SegmentId) -> Segment:
        segment = self.find(segment_id)
        if segment is None:
            raise NotFoundError(
                "Segment not found",
                code="segment.not_found",
                context={"segment_id": str(segment_id)},
            )
        return segment

    def find(self, segment_id: SegmentId) -> Segment | None:
        value = self._state.segments.get(segment_id)
        return deepcopy(value) if value is not None else None

    def find_by_key(self, key: str) -> Segment | None:
        normalized = normalize_segment_key(key)
        for segment in self._state.segments.values():
            if segment.key == normalized:
                return deepcopy(segment)
        return None

    def save(self, segment: Segment) -> None:
        existing = self.find_by_key(segment.key)
        if existing is not None and existing.id != segment.id:
            raise DuplicateError(
                "Segment key already exists",
                code="segment.key.duplicate",
                context={"key": segment.key},
            )
        self._state.segments[segment.id] = deepcopy(segment)

    def search(
        self,
        query: SegmentQuery,
        page: OffsetPageRequest,
    ) -> Page[Segment]:
        values = list(self._state.segments.values())
        if not query.include_archived:
            values = [
                item for item in values if item.status is not SegmentStatus.ARCHIVED
            ]
        if query.status is not None:
            values = [item for item in values if item.status is query.status]
        if query.mode is not None:
            values = [item for item in values if item.mode is query.mode]
        if query.entity_kind is not None:
            values = [
                item for item in values if item.entity_kind == query.entity_kind
            ]
        if query.owner_id is not None:
            values = [item for item in values if item.owner_id == query.owner_id]
        values.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )


class MemorySegmentMembershipRepository:
    """Stored Static/Snapshot memberships."""

    def __init__(self, state: _MemoryState | None = None) -> None:
        self._state = state or _MemoryState()

    def add(self, member: SegmentMember) -> SegmentMember:
        key = (member.segment_id, member.entity)
        if key in self._state.segment_members:
            raise DuplicateError(
                "Segment membership already exists",
                code="segment.member.duplicate",
                context={
                    "segment_id": str(member.segment_id),
                    "entity_kind": member.entity.kind,
                    "entity_id": str(member.entity.id),
                },
            )
        self._state.segment_members[key] = deepcopy(member)
        return deepcopy(member)

    def remove(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        return self._state.segment_members.pop((segment_id, entity), None) is not None

    def contains(self, segment_id: SegmentId, entity: EntityReference) -> bool:
        return (segment_id, entity) in self._state.segment_members

    def list(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest,
    ) -> Page[SegmentMember]:
        values = [
            member
            for (stored_segment_id, _), member in self._state.segment_members.items()
            if stored_segment_id == segment_id
        ]
        values.sort(key=lambda item: (item.added_at, item.entity.kind, str(item.entity.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(deepcopy(selected)),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def count(self, segment_id: SegmentId) -> int:
        return sum(
            1
            for stored_segment_id, _ in self._state.segment_members
            if stored_segment_id == segment_id
        )


class MemorySegmentQueryExecutor:
    """Semantic reference evaluator over the in-memory canonical CRM state."""

    def __init__(self, state: _MemoryState) -> None:
        self._state = state
        self._schemas = default_query_schemas()

    def execute(
        self,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest,
    ) -> Page[EntityReference]:
        schema = self._schemas.get(entity_kind)
        schema.validate(expression)
        values = [
            entity
            for entity in self._entities(entity_kind)
            if self._matches(entity, expression, schema)
        ]
        values.sort(key=lambda item: (item.created_at, str(item.id)))
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(EntityReference(entity_kind, item.id) for item in selected),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def count(self, entity_kind: str, expression: QueryExpression) -> int:
        schema = self._schemas.get(entity_kind)
        schema.validate(expression)
        return sum(
            1
            for entity in self._entities(entity_kind)
            if self._matches(entity, expression, schema)
        )

    def exists(self, entity: EntityReference) -> bool:
        return any(str(item.id) == str(entity.id) for item in self._entities(entity.kind))

    def _entities(self, entity_kind: str) -> tuple[SegmentEntity, ...]:
        if entity_kind == "contact":
            return tuple(self._state.contacts.values())
        if entity_kind == "organization":
            return tuple(self._state.organizations.values())
        if entity_kind == "lead":
            return tuple(self._state.leads.values())
        if entity_kind == "opportunity":
            return tuple(self._state.opportunities.values())
        self._schemas.get(entity_kind)
        raise AssertionError("unreachable")

    def _matches(
        self,
        entity: SegmentEntity,
        expression: QueryExpression,
        schema: object,
    ) -> bool:
        from pycrmkit.segments.schema import QuerySchema

        assert isinstance(schema, QuerySchema)
        if isinstance(expression, Predicate):
            field = schema.field(expression.field)
            return self._predicate(field, getattr(entity, expression.field), expression)
        if isinstance(expression, And):
            return all(self._matches(entity, item, schema) for item in expression.expressions)
        if isinstance(expression, Or):
            return any(self._matches(entity, item, schema) for item in expression.expressions)
        if isinstance(expression, Not):
            return not self._matches(entity, expression.expression, schema)
        raise AssertionError(f"unsupported expression node: {type(expression).__name__}")

    @staticmethod
    def _predicate(
        field: QueryField,
        actual: object,
        predicate: Predicate,
    ) -> bool:
        operator = predicate.operator
        if operator is QueryOperator.IS_NULL:
            return actual is None
        if operator is QueryOperator.IS_NOT_NULL:
            return actual is not None
        if actual is None:
            return False

        left = field.normalize_value(actual)
        raw_right = predicate.value
        assert raw_right is not None

        if operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            assert isinstance(raw_right, tuple)
            values = tuple(field.normalize_value(item) for item in raw_right)
            present = left in values
            return present if operator is QueryOperator.IN else not present

        right = field.normalize_value(raw_right)
        if operator is QueryOperator.EQ:
            return left == right
        if operator is QueryOperator.NE:
            return left != right
        if operator is QueryOperator.LT:
            return bool(cast(Any, left) < cast(Any, right))
        if operator is QueryOperator.LTE:
            return bool(cast(Any, left) <= cast(Any, right))
        if operator is QueryOperator.GT:
            return bool(cast(Any, left) > cast(Any, right))
        if operator is QueryOperator.GTE:
            return bool(cast(Any, left) >= cast(Any, right))

        assert isinstance(left, str) and isinstance(right, str)
        if operator is QueryOperator.CONTAINS:
            return right in left
        if operator is QueryOperator.STARTS_WITH:
            return left.startswith(right)
        if operator is QueryOperator.ENDS_WITH:
            return left.endswith(right)
        raise AssertionError(f"unsupported query operator: {operator}")


__all__ = [
    "MemorySegmentMembershipRepository",
    "MemorySegmentQueryExecutor",
    "MemorySegmentRepository",
]
