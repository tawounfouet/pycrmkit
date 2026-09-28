"""In-memory Segmentation repositories and query evaluator."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from functools import cmp_to_key
from typing import Any, cast

from pycrmkit.contacts import Contact
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldDefinition
from pycrmkit.exceptions import DuplicateError, NotFoundError, ValidationError
from pycrmkit.leads import Lead
from pycrmkit.opportunities import Opportunity
from pycrmkit.organizations import Organization
from pycrmkit.segments import (
    And,
    Not,
    NullOrder,
    Or,
    Predicate,
    QueryExpression,
    QueryOperator,
    RelativeTimeValue,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentQuery,
    SegmentStatus,
    SortDirection,
    SortExpression,
    default_query_schemas,
    normalize_segment_key,
)
from pycrmkit.segments.schema import (
    QueryField,
    QuerySchema,
    query_field_from_custom_definition,
)
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
    """Semantic reference evaluator over canonical in-memory CRM state."""

    def __init__(self, state: _MemoryState) -> None:
        self._state = state
        self._base_schemas = default_query_schemas()

    def validate(
        self,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
    ) -> None:
        schema = self._schema(entity_kind)
        schema.validate(expression)
        for item in ordering:
            field = schema.field(item.field)
            if field.key == "tag":
                raise ValidationError(
                    "tag collection cannot be used as an ordering field",
                    code="segment.query.ordering.invalid_field",
                    context={"field": field.key},
                )

    def execute(
        self,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest,
        *,
        at: datetime,
        ordering: tuple[SortExpression, ...] = (),
    ) -> Page[EntityReference]:
        schema = self._schema(entity_kind)
        self.validate(entity_kind, expression, ordering)
        values = [
            entity
            for entity in self._entities(entity_kind)
            if self._matches(entity, expression, schema, at)
        ]
        values.sort(
            key=cmp_to_key(
                lambda left, right: self._compare_entities(
                    left,
                    right,
                    schema,
                    tuple(ordering),
                )
            )
        )
        total = len(values)
        selected = values[page.offset : page.offset + page.limit]
        return Page(
            items=tuple(EntityReference(entity_kind, item.id) for item in selected),
            limit=page.limit,
            offset=page.offset,
            total=total,
        )

    def count(
        self,
        entity_kind: str,
        expression: QueryExpression,
        *,
        at: datetime,
    ) -> int:
        schema = self._schema(entity_kind)
        schema.validate(expression)
        return sum(
            1
            for entity in self._entities(entity_kind)
            if self._matches(entity, expression, schema, at)
        )

    def exists(self, entity: EntityReference) -> bool:
        return any(str(item.id) == str(entity.id) for item in self._entities(entity.kind))

    def _schema(self, entity_kind: str) -> QuerySchema:
        base = self._base_schemas.get(entity_kind)
        custom_fields: list[QueryField] = []
        for versions in self._state.custom_field_definitions.values():
            definition = versions[-1]
            if entity_kind not in definition.applies_to:
                continue
            field = query_field_from_custom_definition(definition)
            if field is not None:
                custom_fields.append(field)
        custom_fields.sort(key=lambda item: item.key)
        return QuerySchema(
            entity_kind=base.entity_kind,
            fields=(*base.fields, *custom_fields),
            version=base.version,
        )

    def _entities(self, entity_kind: str) -> tuple[SegmentEntity, ...]:
        if entity_kind == "contact":
            return tuple(self._state.contacts.values())
        if entity_kind == "organization":
            return tuple(self._state.organizations.values())
        if entity_kind == "lead":
            return tuple(self._state.leads.values())
        if entity_kind == "opportunity":
            return tuple(self._state.opportunities.values())
        self._base_schemas.get(entity_kind)
        raise AssertionError("unreachable")

    def _matches(
        self,
        entity: SegmentEntity,
        expression: QueryExpression,
        schema: QuerySchema,
        at: datetime,
    ) -> bool:
        if isinstance(expression, Predicate):
            field = schema.field(expression.field)
            actual = self._field_value(entity, field.key)
            if field.key == "tag":
                return self._tag_predicate(tuple(actual or ()), expression)
            return self._predicate(field, actual, expression, at)
        if isinstance(expression, And):
            return all(
                self._matches(entity, item, schema, at)
                for item in expression.expressions
            )
        if isinstance(expression, Or):
            return any(
                self._matches(entity, item, schema, at)
                for item in expression.expressions
            )
        if isinstance(expression, Not):
            return not self._matches(entity, expression.expression, schema, at)
        raise AssertionError(f"unsupported expression node: {type(expression).__name__}")

    def _field_value(self, entity: SegmentEntity, key: str) -> object:
        if key == "tag":
            reference = EntityReference(self._entity_kind(entity), entity.id)
            names = []
            for tag_id, assigned in self._state.tag_assignments:
                if assigned == reference:
                    tag = self._state.tags.get(tag_id)
                    if tag is not None:
                        names.append(tag.name.normalized)
            return tuple(sorted(names))
        if key.startswith("custom."):
            custom_key = key.split(".", 1)[1]
            definition = self._custom_definition(custom_key, self._entity_kind(entity))
            if definition is None:
                return None
            value = self._state.custom_field_values.get(
                (
                    definition.id,
                    EntityReference(self._entity_kind(entity), entity.id),
                )
            )
            return None if value is None else value.value
        return getattr(entity, key)

    def _custom_definition(
        self,
        key: str,
        entity_kind: str,
    ) -> CustomFieldDefinition | None:
        for versions in self._state.custom_field_definitions.values():
            definition = versions[-1]
            if (
                definition.key == key
                and definition.active
                and entity_kind in definition.applies_to
            ):
                return definition
        return None

    @staticmethod
    def _entity_kind(entity: SegmentEntity) -> str:
        if isinstance(entity, Contact):
            return "contact"
        if isinstance(entity, Organization):
            return "organization"
        if isinstance(entity, Lead):
            return "lead"
        if isinstance(entity, Opportunity):
            return "opportunity"
        raise AssertionError(type(entity).__name__)

    @staticmethod
    def _tag_predicate(tags: tuple[str, ...], predicate: Predicate) -> bool:
        operator = predicate.operator
        if operator is QueryOperator.IS_NULL:
            return not tags
        if operator is QueryOperator.IS_NOT_NULL:
            return bool(tags)
        raw = predicate.value
        assert raw is not None

        def normalize(value: object) -> str:
            if not isinstance(value, str):
                raise ValidationError(
                    "tag query values must be strings",
                    code="segment.query.invalid_value",
                    context={"field": "tag"},
                )
            return " ".join(value.strip().split()).casefold()

        if operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            assert isinstance(raw, tuple)
            wanted = {normalize(item) for item in raw}
            present = any(tag in wanted for tag in tags)
            return present if operator is QueryOperator.IN else not present

        right = normalize(raw)
        if operator is QueryOperator.EQ:
            return right in tags
        if operator is QueryOperator.NE:
            return right not in tags
        if operator is QueryOperator.CONTAINS:
            return any(right in tag for tag in tags)
        if operator is QueryOperator.STARTS_WITH:
            return any(tag.startswith(right) for tag in tags)
        if operator is QueryOperator.ENDS_WITH:
            return any(tag.endswith(right) for tag in tags)
        raise ValidationError(
            "operator is not supported for tag filtering",
            code="segment.query.invalid_operator",
            context={"field": "tag", "operator": operator.value},
        )

    @staticmethod
    def _predicate(
        field: QueryField,
        actual: object,
        predicate: Predicate,
        at: datetime,
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

        if isinstance(raw_right, RelativeTimeValue):
            resolved = raw_right.resolve(at)
            raw_right = resolved.date() if field.type.value == "date" else resolved

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

    def _compare_entities(
        self,
        left: SegmentEntity,
        right: SegmentEntity,
        schema: QuerySchema,
        ordering: tuple[SortExpression, ...],
    ) -> int:
        rules = ordering or (SortExpression("created_at"),)
        for rule in rules:
            field = schema.field(rule.field)
            left_value = self._field_value(left, field.key)
            right_value = self._field_value(right, field.key)
            compared = self._compare_values(
                field,
                left_value,
                right_value,
                direction=rule.direction,
                null_order=rule.null_order,
            )
            if compared:
                return compared
        left_id = str(left.id)
        right_id = str(right.id)
        return (left_id > right_id) - (left_id < right_id)

    @staticmethod
    def _compare_values(
        field: QueryField,
        left: object,
        right: object,
        *,
        direction: SortDirection,
        null_order: NullOrder,
    ) -> int:
        if left is None or right is None:
            if left is None and right is None:
                return 0
            null_first = null_order is NullOrder.FIRST
            result = -1 if left is None else 1
            return result if null_first else -result
        left_value = field.normalize_value(left)
        right_value = field.normalize_value(right)
        result = (cast(Any, left_value) > cast(Any, right_value)) - (
            cast(Any, left_value) < cast(Any, right_value)
        )
        return result if direction is SortDirection.ASC else -result


__all__ = [
    "MemorySegmentMembershipRepository",
    "MemorySegmentQueryExecutor",
    "MemorySegmentRepository",
]
