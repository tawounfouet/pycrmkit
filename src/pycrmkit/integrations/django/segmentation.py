"""Django ORM Segmentation persistence and query execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import F, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Lower

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import EntityId, UUIDId
from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import as_utc
from pycrmkit.exceptions import (
    ConflictError,
    DuplicateError,
    NotFoundError,
    ValidationError,
)
from pycrmkit.integrations.django.models import (
    ContactModel,
    OrganizationModel,
    SavedQueryModel,
    SegmentMemberModel,
    SegmentModel,
)
from pycrmkit.organizations import OrganizationId
from pycrmkit.saved_queries import (
    SavedQuery,
    SavedQueryId,
    SavedQueryQuery,
    SavedQueryStatus,
    SavedQueryVisibility,
    normalize_saved_query_key,
)
from pycrmkit.segments import (
    And,
    Not,
    NullOrder,
    Or,
    Predicate,
    QueryExpression,
    QueryField,
    QueryFieldType,
    QueryOperator,
    QuerySchema,
    RelativeTimeValue,
    Segment,
    SegmentId,
    SegmentMember,
    SegmentMode,
    SegmentQuery,
    SegmentStatus,
    SortDirection,
    SortExpression,
    default_query_schemas,
    expression_from_dict,
    expression_to_dict,
    normalize_segment_key,
)
from pycrmkit.segments.schema import iter_predicates


def _reference(kind: str, identifier: str) -> EntityReference:
    if kind == "contact":
        return EntityReference(kind, ContactId.parse(identifier))
    if kind == "organization":
        return EntityReference(kind, OrganizationId.parse(identifier))
    raise ValidationError(
        "Django Segmentation supports Contact and Organization references",
        code="segment.query.django.unsupported_entity_kind",
        context={"entity_kind": kind},
    )


def _page(
    queryset: QuerySet[Any],
    page: OffsetPageRequest,
    mapper: Any,
) -> Page[Any]:
    total = queryset.count()
    rows = queryset[page.offset : page.offset + page.limit]
    return Page(
        items=tuple(mapper(row) for row in rows),
        limit=page.limit,
        offset=page.offset,
        total=total,
    )


def _segment_from_model(model: SegmentModel) -> Segment:
    return Segment(
        id=SegmentId.parse(model.id),
        created_at=as_utc(model.created_at),
        updated_at=as_utc(model.updated_at),
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
        archived_at=(
            as_utc(model.archived_at)
            if model.archived_at is not None
            else None
        ),
    )


def _member_from_model(model: SegmentMemberModel) -> SegmentMember:
    return SegmentMember(
        segment_id=SegmentId.parse(model.segment_id),
        entity=_reference(model.entity_kind, model.entity_id),
        added_at=as_utc(model.added_at),
        source=model.source,
        actor_id=model.actor_id,
        metadata=dict(model.metadata_json or {}),
    )


def _saved_query_from_model(model: SavedQueryModel) -> SavedQuery:
    return SavedQuery(
        id=SavedQueryId.parse(model.query_id),
        created_at=as_utc(model.created_at),
        updated_at=as_utc(model.updated_at),
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
        archived_at=(
            as_utc(model.archived_at)
            if model.archived_at is not None
            else None
        ),
    )


class DjangoSegmentRepository:
    """Django current-state Segment repository."""

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
        model = SegmentModel.objects.filter(pk=str(segment_id)).first()
        return None if model is None else _segment_from_model(model)

    def find_by_key(self, key: str) -> Segment | None:
        model = SegmentModel.objects.filter(
            key=normalize_segment_key(key)
        ).first()
        return None if model is None else _segment_from_model(model)

    def save(self, segment: Segment) -> None:
        existing = SegmentModel.objects.filter(key=segment.key).first()
        if existing is not None and existing.id != str(segment.id):
            raise DuplicateError(
                "Segment key already exists",
                code="segment.key.duplicate",
                context={"key": segment.key},
            )
        current = SegmentModel.objects.filter(pk=str(segment.id)).first()
        if current is not None and segment.revision < current.revision:
            raise ConflictError(
                "Segment revision has changed",
                code="segment.revision.conflict",
                context={
                    "expected_at_least": current.revision,
                    "actual": segment.revision,
                },
            )
        SegmentModel.objects.update_or_create(
            pk=str(segment.id),
            defaults={
                "key": segment.key,
                "name": segment.name,
                "entity_kind": segment.entity_kind,
                "mode": segment.mode.value,
                "description": segment.description,
                "status": segment.status.value,
                "query_json": (
                    expression_to_dict(segment.query)
                    if segment.query is not None
                    else None
                ),
                "saved_query_id": (
                    str(segment.saved_query_id)
                    if segment.saved_query_id is not None
                    else None
                ),
                "saved_query_revision": segment.saved_query_revision,
                "owner_id": (
                    str(segment.owner_id)
                    if segment.owner_id is not None
                    else None
                ),
                "revision": segment.revision,
                "metadata_json": dict(segment.metadata),
                "archived_at": segment.archived_at,
                "created_at": segment.created_at,
                "updated_at": segment.updated_at,
            },
        )

    def search(
        self,
        query: SegmentQuery,
        page: OffsetPageRequest,
    ) -> Page[Segment]:
        queryset = SegmentModel.objects.all()
        if not query.include_archived:
            queryset = queryset.exclude(
                status=SegmentStatus.ARCHIVED.value
            )
        if query.status is not None:
            queryset = queryset.filter(status=query.status.value)
        if query.mode is not None:
            queryset = queryset.filter(mode=query.mode.value)
        if query.entity_kind is not None:
            queryset = queryset.filter(entity_kind=query.entity_kind)
        if query.owner_id is not None:
            queryset = queryset.filter(owner_id=str(query.owner_id))
        queryset = queryset.order_by("created_at", "id")
        return _page(queryset, page, _segment_from_model)


class DjangoSegmentMembershipRepository:
    """Django stored membership repository for Static/Snapshot Segments."""

    def add(self, member: SegmentMember) -> SegmentMember:
        if SegmentMemberModel.objects.filter(
            segment_id=str(member.segment_id),
            entity_kind=member.entity.kind,
            entity_id=str(member.entity.id),
        ).exists():
            raise DuplicateError(
                "Segment membership already exists",
                code="segment.member.duplicate",
                context={
                    "segment_id": str(member.segment_id),
                    "entity_kind": member.entity.kind,
                    "entity_id": str(member.entity.id),
                },
            )
        SegmentMemberModel.objects.create(
            segment_id=str(member.segment_id),
            entity_kind=member.entity.kind,
            entity_id=str(member.entity.id),
            added_at=member.added_at,
            source=member.source,
            actor_id=member.actor_id,
            metadata_json=dict(member.metadata),
        )
        return member

    def add_many(
        self,
        members: tuple[SegmentMember, ...],
    ) -> tuple[SegmentMember, ...]:
        keys = [
            (str(member.segment_id), member.entity.kind, str(member.entity.id))
            for member in members
        ]
        if len(keys) != len(set(keys)):
            raise DuplicateError(
                "Segment membership batch contains duplicates",
                code="segment.member.batch_duplicate",
            )
        for segment_id, entity_kind, entity_id in keys:
            if SegmentMemberModel.objects.filter(
                segment_id=segment_id,
                entity_kind=entity_kind,
                entity_id=entity_id,
            ).exists():
                raise DuplicateError(
                    "Segment membership already exists",
                    code="segment.member.duplicate",
                    context={
                        "segment_id": segment_id,
                        "entity_kind": entity_kind,
                        "entity_id": entity_id,
                    },
                )
        SegmentMemberModel.objects.bulk_create(
            [
                SegmentMemberModel(
                    segment_id=str(member.segment_id),
                    entity_kind=member.entity.kind,
                    entity_id=str(member.entity.id),
                    added_at=member.added_at,
                    source=member.source,
                    actor_id=member.actor_id,
                    metadata_json=dict(member.metadata),
                )
                for member in members
            ]
        )
        return members

    def remove(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
    ) -> bool:
        deleted, _ = SegmentMemberModel.objects.filter(
            segment_id=str(segment_id),
            entity_kind=entity.kind,
            entity_id=str(entity.id),
        ).delete()
        return deleted > 0

    def remove_many(
        self,
        segment_id: SegmentId,
        entities: tuple[EntityReference, ...],
    ) -> int:
        unique = tuple(dict.fromkeys(entities))
        if not unique:
            return 0
        targets = Q()
        for entity in unique:
            targets |= Q(
                entity_kind=entity.kind,
                entity_id=str(entity.id),
            )
        deleted, _ = SegmentMemberModel.objects.filter(
            Q(segment_id=str(segment_id)) & targets
        ).delete()
        return deleted

    def contains(
        self,
        segment_id: SegmentId,
        entity: EntityReference,
    ) -> bool:
        return SegmentMemberModel.objects.filter(
            segment_id=str(segment_id),
            entity_kind=entity.kind,
            entity_id=str(entity.id),
        ).exists()

    def list(
        self,
        segment_id: SegmentId,
        page: OffsetPageRequest,
    ) -> Page[SegmentMember]:
        queryset = SegmentMemberModel.objects.filter(
            segment_id=str(segment_id)
        ).order_by(
            "added_at",
            "entity_kind",
            "entity_id",
            "id",
        )
        return _page(queryset, page, _member_from_model)

    def count(self, segment_id: SegmentId) -> int:
        return SegmentMemberModel.objects.filter(
            segment_id=str(segment_id)
        ).count()


class DjangoSavedQueryRepository:
    """Django append-only SavedQuery revision repository."""

    def get(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery:
        query = self.find(query_id, revision)
        if query is None:
            raise NotFoundError(
                "Saved query not found",
                code=(
                    "saved_query.not_found"
                    if revision is None
                    else "saved_query.revision.not_found"
                ),
                context={
                    "saved_query_id": str(query_id),
                    "revision": revision,
                },
            )
        return query

    def find(
        self,
        query_id: SavedQueryId,
        revision: int | None = None,
    ) -> SavedQuery | None:
        queryset = SavedQueryModel.objects.filter(query_id=str(query_id))
        if revision is None:
            model = queryset.order_by("-revision").first()
        else:
            model = queryset.filter(revision=revision).first()
        return None if model is None else _saved_query_from_model(model)

    def find_by_key(self, key: str) -> SavedQuery | None:
        model = (
            SavedQueryModel.objects.filter(
                key=normalize_saved_query_key(key)
            )
            .order_by("-revision")
            .first()
        )
        return None if model is None else _saved_query_from_model(model)

    def save(self, query: SavedQuery) -> None:
        current = (
            SavedQueryModel.objects.filter(query_id=str(query.id))
            .order_by("-revision")
            .first()
        )
        existing_by_key = self.find_by_key(query.key)
        if (
            existing_by_key is not None
            and existing_by_key.id != query.id
        ):
            raise DuplicateError(
                "Saved-query key already exists",
                code="saved_query.key.duplicate",
                context={"key": query.key},
            )
        expected = 1 if current is None else current.revision + 1
        if query.revision != expected:
            raise ConflictError(
                "Saved-query revisions must be appended sequentially",
                code="saved_query.revision.conflict",
                context={"expected": expected, "actual": query.revision},
            )
        if current is not None and query.key != current.key:
            raise ConflictError(
                "Saved-query key is immutable",
                code="saved_query.key.immutable",
            )
        if current is not None and query.entity_kind != current.entity_kind:
            raise ConflictError(
                "Saved-query entity kind is immutable",
                code="saved_query.entity_kind.immutable",
            )
        SavedQueryModel.objects.create(
            query_id=str(query.id),
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
                str(query.owner_id)
                if query.owner_id is not None
                else None
            ),
            visibility=query.visibility.value,
            status=query.status.value,
            metadata_json=dict(query.metadata),
            archived_at=query.archived_at,
            created_at=query.created_at,
            updated_at=query.updated_at,
        )

    def list_revisions(
        self,
        query_id: SavedQueryId,
    ) -> tuple[SavedQuery, ...]:
        return tuple(
            _saved_query_from_model(model)
            for model in SavedQueryModel.objects.filter(
                query_id=str(query_id)
            ).order_by("revision")
        )

    def search(
        self,
        query: SavedQueryQuery,
        page: OffsetPageRequest,
    ) -> Page[SavedQuery]:
        latest_revision = (
            SavedQueryModel.objects.filter(query_id=OuterRef("query_id"))
            .order_by("-revision")
            .values("revision")[:1]
        )
        queryset = SavedQueryModel.objects.annotate(
            latest_revision=Subquery(latest_revision)
        ).filter(revision=F("latest_revision"))
        if not query.include_archived:
            queryset = queryset.exclude(
                status=SavedQueryStatus.ARCHIVED.value
            )
        if query.status is not None:
            queryset = queryset.filter(status=query.status.value)
        if query.visibility is not None:
            queryset = queryset.filter(visibility=query.visibility.value)
        if query.entity_kind is not None:
            queryset = queryset.filter(entity_kind=query.entity_kind)
        if query.owner_id is not None:
            queryset = queryset.filter(owner_id=str(query.owner_id))
        queryset = queryset.order_by(Lower("name"), "query_id")
        return _page(queryset, page, _saved_query_from_model)


class DjangoSegmentQueryExecutor:
    """Compile portable Segment predicates into Django ORM queries.

    The current Django persistence bridge owns Contact and Organization state,
    so this executor intentionally limits evaluation to those entity kinds.
    """

    def __init__(self) -> None:
        self._base_schemas = default_query_schemas()

    def validate(
        self,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
    ) -> None:
        schema = self._schema(entity_kind)
        for predicate in iter_predicates(expression):
            self._ensure_supported_field(predicate.field)
        for item in ordering:
            self._ensure_supported_field(item.field)
            schema.field(item.field)
        schema.validate(expression)

    def execute(
        self,
        entity_kind: str,
        expression: QueryExpression,
        page: OffsetPageRequest,
        *,
        at: datetime,
        ordering: tuple[SortExpression, ...] = (),
    ) -> Page[EntityReference]:
        self.validate(entity_kind, expression, ordering)
        schema = self._schema(entity_kind)
        model = self._model(entity_kind)
        queryset: QuerySet[Any] = model.objects.all()
        queryset, names = self._annotate(
            queryset,
            schema,
            expression,
            ordering,
        )
        queryset = queryset.filter(
            self._compile(expression, schema, names, at)
        )
        total = queryset.count()
        queryset = queryset.order_by(
            *self._ordering(schema, names, ordering)
        )
        identifiers = tuple(
            str(value)
            for value in queryset.values_list(
                "id",
                flat=True,
            )[page.offset : page.offset + page.limit]
        )
        return Page(
            items=tuple(
                _reference(entity_kind, identifier)
                for identifier in identifiers
            ),
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
        self.validate(entity_kind, expression)
        schema = self._schema(entity_kind)
        model = self._model(entity_kind)
        queryset: QuerySet[Any] = model.objects.all()
        queryset, names = self._annotate(
            queryset,
            schema,
            expression,
            (),
        )
        return queryset.filter(
            self._compile(expression, schema, names, at)
        ).count()

    def exists(self, entity: EntityReference) -> bool:
        model = self._model(entity.kind)
        return bool(model.objects.filter(pk=str(entity.id)).exists())

    def _schema(self, entity_kind: str) -> QuerySchema:
        kind = entity_kind.strip().casefold()
        self._model(kind)
        return self._base_schemas.get(kind)

    @staticmethod
    def _model(entity_kind: str) -> Any:
        models = {
            "contact": ContactModel,
            "organization": OrganizationModel,
        }
        try:
            return models[entity_kind.strip().casefold()]
        except KeyError as exc:
            raise ValidationError(
                "Django Segmentation supports Contact and Organization queries",
                code="segment.query.django.unsupported_entity_kind",
                context={"entity_kind": entity_kind},
            ) from exc

    @staticmethod
    def _ensure_supported_field(field: str) -> None:
        if field == "tag" or field.startswith("custom."):
            raise ValidationError(
                "Django Segmentation does not yet expose Tag or Custom Field query state",
                code="segment.query.django.unsupported_field",
                context={"field": field},
            )

    @staticmethod
    def _annotate(
        queryset: QuerySet[Any],
        schema: QuerySchema,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...],
    ) -> tuple[QuerySet[Any], dict[str, str]]:
        fields = {
            *(predicate.field for predicate in iter_predicates(expression)),
            *(item.field for item in ordering),
        }
        names: dict[str, str] = {}
        annotations: dict[str, Any] = {}
        for index, key in enumerate(sorted(fields)):
            field = schema.field(key)
            if field.type in {
                QueryFieldType.STRING,
                QueryFieldType.ENUM,
            }:
                alias = f"_pycrmkit_q_{index}"
                annotations[alias] = Lower(F(key))
                names[key] = alias
            else:
                names[key] = key
        if annotations:
            queryset = queryset.annotate(**annotations)
        return queryset, names

    def _compile(
        self,
        expression: QueryExpression,
        schema: QuerySchema,
        names: dict[str, str],
        at: datetime,
    ) -> Q:
        if isinstance(expression, Predicate):
            field = schema.field(expression.field)
            return self._predicate(
                names[field.key],
                field,
                expression,
                at,
            )
        if isinstance(expression, And):
            result = Q()
            for child in expression.expressions:
                result &= self._compile(child, schema, names, at)
            return result
        if isinstance(expression, Or):
            result = Q(pk__in=[])
            for child in expression.expressions:
                result |= self._compile(child, schema, names, at)
            return result
        if isinstance(expression, Not):
            return ~self._compile(
                expression.expression,
                schema,
                names,
                at,
            )
        raise AssertionError(type(expression).__name__)

    @staticmethod
    def _predicate(
        name: str,
        field: QueryField,
        predicate: Predicate,
        at: datetime,
    ) -> Q:
        operator = predicate.operator
        if operator is QueryOperator.IS_NULL:
            return Q(**{f"{name}__isnull": True})
        if operator is QueryOperator.IS_NOT_NULL:
            return Q(**{f"{name}__isnull": False})

        raw = predicate.value
        assert raw is not None
        if isinstance(raw, RelativeTimeValue):
            resolved = raw.resolve(at)
            raw = (
                resolved.date()
                if field.type is QueryFieldType.DATE
                else resolved
            )

        non_null = Q(**{f"{name}__isnull": False})
        if operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            assert isinstance(raw, tuple)
            values = tuple(field.normalize_value(item) for item in raw)
            condition = Q(**{f"{name}__in": values})
            return (
                non_null & condition
                if operator is QueryOperator.IN
                else non_null & ~condition
            )

        value = field.normalize_value(raw)
        lookups = {
            QueryOperator.EQ: "",
            QueryOperator.NE: "",
            QueryOperator.LT: "__lt",
            QueryOperator.LTE: "__lte",
            QueryOperator.GT: "__gt",
            QueryOperator.GTE: "__gte",
            QueryOperator.CONTAINS: "__contains",
            QueryOperator.STARTS_WITH: "__startswith",
            QueryOperator.ENDS_WITH: "__endswith",
        }
        lookup = lookups[operator]
        condition = Q(**{f"{name}{lookup}": value})
        if operator is QueryOperator.NE:
            return non_null & ~condition
        return non_null & condition

    @staticmethod
    def _ordering(
        schema: QuerySchema,
        names: dict[str, str],
        ordering: tuple[SortExpression, ...],
    ) -> tuple[Any, ...]:
        rules = ordering or (SortExpression("created_at"),)
        values: list[Any] = []
        for rule in rules:
            schema.field(rule.field)
            name = names.get(rule.field, rule.field)
            expression = F(name)
            if rule.direction is SortDirection.ASC:
                order = (
                    expression.asc(nulls_first=True)
                    if rule.null_order is NullOrder.FIRST
                    else expression.asc(nulls_last=True)
                )
            else:
                order = (
                    expression.desc(nulls_first=True)
                    if rule.null_order is NullOrder.FIRST
                    else expression.desc(nulls_last=True)
                )
            values.append(order)
        values.append(F("id").asc())
        return tuple(values)


__all__ = [
    "DjangoSavedQueryRepository",
    "DjangoSegmentMembershipRepository",
    "DjangoSegmentQueryExecutor",
    "DjangoSegmentRepository",
]
