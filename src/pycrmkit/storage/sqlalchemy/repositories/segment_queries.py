"""SQLAlchemy compiler/executor for portable Segment query expressions."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from sqlalchemy import Numeric, and_, cast as sql_cast, exists, false, func, not_, or_, select
from sqlalchemy.orm import Session

from pycrmkit.core.pagination import OffsetPageRequest, Page
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldDefinition
from pycrmkit.exceptions import ValidationError
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
    SortDirection,
    SortExpression,
    default_query_schemas,
)
from pycrmkit.segments.schema import (
    iter_predicates,
    query_field_from_custom_definition,
)
from pycrmkit.storage.sqlalchemy.mappers import entity_reference
from pycrmkit.storage.sqlalchemy.models.contact import ContactModel
from pycrmkit.storage.sqlalchemy.models.custom_field import CustomFieldValueModel
from pycrmkit.storage.sqlalchemy.models.lead import LeadModel
from pycrmkit.storage.sqlalchemy.models.opportunity import OpportunityModel
from pycrmkit.storage.sqlalchemy.models.organization import OrganizationModel
from pycrmkit.storage.sqlalchemy.models.tag import TagAssignmentModel, TagModel
from pycrmkit.storage.sqlalchemy.repositories.custom_fields import (
    SQLAlchemyCustomFieldRepository,
)


class SQLAlchemySegmentQueryExecutor:
    """Compile the provider-neutral query AST into database-side SQL."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._base_schemas = default_query_schemas()

    def validate(
        self,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...] = (),
    ) -> None:
        schema = self._schema(entity_kind, expression, ordering)
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
        schema = self._schema(entity_kind, expression, ordering)
        schema.validate(expression)
        self.validate(entity_kind, expression, ordering)

        model = self._entity_model(entity_kind)
        predicate = self._compile_expression(
            model,
            entity_kind,
            expression,
            schema,
            at,
        )
        count_statement = (
            select(func.count())
            .select_from(model)
            .where(predicate)
        )
        total = int(self.session.scalar(count_statement) or 0)

        statement = select(model.id).where(predicate)
        statement = statement.order_by(
            *self._ordering(model, entity_kind, schema, ordering)
        )
        identifiers = self.session.scalars(
            statement.offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=tuple(
                entity_reference(entity_kind, str(identifier))
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
        schema = self._schema(entity_kind, expression, ())
        schema.validate(expression)
        model = self._entity_model(entity_kind)
        predicate = self._compile_expression(
            model,
            entity_kind,
            expression,
            schema,
            at,
        )
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(model)
                .where(predicate)
            )
            or 0
        )

    def exists(self, entity: EntityReference) -> bool:
        model = self._entity_model(entity.kind)
        return (
            self.session.scalar(
                select(model.id)
                .where(model.id == str(entity.id))
                .limit(1)
            )
            is not None
        )

    def _schema(
        self,
        entity_kind: str,
        expression: QueryExpression,
        ordering: tuple[SortExpression, ...],
    ) -> QuerySchema:
        base = self._base_schemas.get(entity_kind)
        custom_keys = {
            field.split(".", 1)[1]
            for field in (
                *(predicate.field for predicate in iter_predicates(expression)),
                *(item.field for item in ordering),
            )
            if field.startswith("custom.")
        }
        custom_fields: list[QueryField] = []
        for key in sorted(custom_keys):
            definition = self._custom_definition(entity_kind, key)
            if definition is None:
                continue
            field = query_field_from_custom_definition(definition)
            if field is not None:
                custom_fields.append(field)
        return QuerySchema(
            entity_kind=base.entity_kind,
            fields=(*base.fields, *custom_fields),
            version=base.version,
        )

    def _custom_definition(
        self,
        entity_kind: str,
        key: str,
    ) -> CustomFieldDefinition | None:
        definition = SQLAlchemyCustomFieldRepository(
            self.session
        ).find_definition_by_key(key)
        if (
            definition is None
            or not definition.active
            or entity_kind not in definition.applies_to
        ):
            return None
        return definition

    @staticmethod
    def _entity_model(entity_kind: str) -> Any:
        models = {
            "contact": ContactModel,
            "organization": OrganizationModel,
            "lead": LeadModel,
            "opportunity": OpportunityModel,
        }
        try:
            return models[entity_kind.strip().casefold()]
        except KeyError as exc:
            raise ValidationError(
                "unsupported segment entity kind",
                code="segment.entity_kind.unsupported",
                context={"entity_kind": entity_kind},
            ) from exc

    def _compile_expression(
        self,
        model: Any,
        entity_kind: str,
        expression: QueryExpression,
        schema: QuerySchema,
        at: datetime,
    ) -> Any:
        if isinstance(expression, Predicate):
            field = schema.field(expression.field)
            if field.key == "tag":
                return self._tag_predicate(
                    model,
                    entity_kind,
                    expression,
                )
            if field.key.startswith("custom."):
                return self._custom_predicate(
                    model,
                    entity_kind,
                    field,
                    expression,
                    at,
                )
            return self._scalar_predicate(
                self._base_column(model, field.key),
                field,
                expression,
                at,
            )
        if isinstance(expression, And):
            return and_(
                *(
                    self._compile_expression(
                        model,
                        entity_kind,
                        child,
                        schema,
                        at,
                    )
                    for child in expression.expressions
                )
            )
        if isinstance(expression, Or):
            return or_(
                *(
                    self._compile_expression(
                        model,
                        entity_kind,
                        child,
                        schema,
                        at,
                    )
                    for child in expression.expressions
                )
            )
        if isinstance(expression, Not):
            return not_(
                self._compile_expression(
                    model,
                    entity_kind,
                    expression.expression,
                    schema,
                    at,
                )
            )
        raise AssertionError(type(expression).__name__)

    @staticmethod
    def _base_column(model: Any, key: str) -> Any:
        try:
            return getattr(model, key)
        except AttributeError as exc:
            raise ValidationError(
                "query field has no SQLAlchemy mapping",
                code="segment.query.invalid_field",
                context={"field": key},
            ) from exc

    def _scalar_predicate(
        self,
        column: Any,
        field: QueryField,
        predicate: Predicate,
        at: datetime,
    ) -> Any:
        operator = predicate.operator
        if operator is QueryOperator.IS_NULL:
            return column.is_(None)
        if operator is QueryOperator.IS_NOT_NULL:
            return column.is_not(None)

        value = self._resolved_value(field, predicate.value, at)
        comparable = self._normalized_sql_value(column, field)
        condition = self._comparison(
            comparable,
            operator,
            value,
        )
        # Portable query semantics are two-valued: non-null comparisons against
        # an absent value are false, so NOT(predicate) becomes true for nulls.
        return func.coalesce(condition, false())

    def _tag_predicate(
        self,
        model: Any,
        entity_kind: str,
        predicate: Predicate,
    ) -> Any:
        base = (
            select(TagAssignmentModel.id)
            .join(TagModel, TagModel.id == TagAssignmentModel.tag_id)
            .where(
                TagAssignmentModel.entity_kind == entity_kind,
                TagAssignmentModel.entity_id == model.id,
            )
        )
        if predicate.operator is QueryOperator.IS_NULL:
            return ~exists(base)
        if predicate.operator is QueryOperator.IS_NOT_NULL:
            return exists(base)

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

        operator = predicate.operator
        if operator in {QueryOperator.IN, QueryOperator.NOT_IN}:
            assert isinstance(raw, tuple)
            values = tuple(normalize(item) for item in raw)
            matched = exists(base.where(TagModel.normalized_name.in_(values)))
            return matched if operator is QueryOperator.IN else ~matched

        value = normalize(raw)
        name = TagModel.normalized_name
        if operator is QueryOperator.EQ:
            matched = exists(base.where(name == value))
        elif operator is QueryOperator.NE:
            return ~exists(base.where(name == value))
        elif operator is QueryOperator.CONTAINS:
            matched = exists(base.where(name.contains(value, autoescape=True)))
        elif operator is QueryOperator.STARTS_WITH:
            matched = exists(base.where(name.startswith(value, autoescape=True)))
        elif operator is QueryOperator.ENDS_WITH:
            matched = exists(base.where(name.endswith(value, autoescape=True)))
        else:
            raise ValidationError(
                "operator is not supported for tag filtering",
                code="segment.query.invalid_operator",
                context={"field": "tag", "operator": operator.value},
            )
        return matched

    def _custom_predicate(
        self,
        model: Any,
        entity_kind: str,
        field: QueryField,
        predicate: Predicate,
        at: datetime,
    ) -> Any:
        definition = self._custom_definition(
            entity_kind,
            field.key.split(".", 1)[1],
        )
        if definition is None:
            raise ValidationError(
                "query field is not available for entity kind",
                code="segment.query.invalid_field",
                context={"entity_kind": entity_kind, "field": field.key},
            )

        raw_json_value = CustomFieldValueModel.value_json["value"]
        scalar = self._custom_scalar(raw_json_value, field)
        base = select(CustomFieldValueModel.id).where(
            CustomFieldValueModel.definition_id == str(definition.id),
            CustomFieldValueModel.entity_kind == entity_kind,
            CustomFieldValueModel.entity_id == model.id,
        )

        if predicate.operator is QueryOperator.IS_NULL:
            return ~exists(base.where(scalar.is_not(None)))
        if predicate.operator is QueryOperator.IS_NOT_NULL:
            return exists(base.where(scalar.is_not(None)))

        value = self._resolved_value(field, predicate.value, at)
        condition = self._comparison(
            self._normalized_sql_value(scalar, field),
            predicate.operator,
            value,
        )
        return exists(base.where(func.coalesce(condition, false())))

    @staticmethod
    def _custom_scalar(raw_json_value: Any, field: QueryField) -> Any:
        if field.type is QueryFieldType.INTEGER:
            return raw_json_value.as_integer()
        if field.type is QueryFieldType.BOOLEAN:
            return raw_json_value.as_boolean()
        if field.type is QueryFieldType.DECIMAL:
            return sql_cast(raw_json_value.as_string(), Numeric(38, 12))
        return raw_json_value.as_string()

    @staticmethod
    def _normalized_sql_value(column: Any, field: QueryField) -> Any:
        if field.type in {QueryFieldType.STRING, QueryFieldType.ENUM}:
            return func.lower(column)
        return column

    @staticmethod
    def _resolved_value(
        field: QueryField,
        raw: object | None,
        at: datetime,
    ) -> object:
        assert raw is not None
        value: object = raw
        if isinstance(value, RelativeTimeValue):
            resolved = value.resolve(at)
            value = (
                resolved.date()
                if field.type is QueryFieldType.DATE
                else resolved
            )
        normalized = field.normalize_value(value)
        if field.type is QueryFieldType.DATETIME and field.key.startswith("custom."):
            return cast(datetime, normalized).isoformat()
        if field.type is QueryFieldType.DATE and field.key.startswith("custom."):
            return normalized.isoformat()  # type: ignore[union-attr]
        if field.type is QueryFieldType.DECIMAL and field.key.startswith("custom."):
            return cast(Decimal, normalized)
        return normalized

    @staticmethod
    def _comparison(
        column: Any,
        operator: QueryOperator,
        value: object,
    ) -> Any:
        if operator is QueryOperator.EQ:
            return column == value
        if operator is QueryOperator.NE:
            return column != value
        if operator is QueryOperator.LT:
            return column < value
        if operator is QueryOperator.LTE:
            return column <= value
        if operator is QueryOperator.GT:
            return column > value
        if operator is QueryOperator.GTE:
            return column >= value
        if operator is QueryOperator.IN:
            assert isinstance(value, tuple)
            return column.in_(value)
        if operator is QueryOperator.NOT_IN:
            assert isinstance(value, tuple)
            return column.not_in(value)
        if operator is QueryOperator.CONTAINS:
            assert isinstance(value, str)
            return column.contains(value, autoescape=True)
        if operator is QueryOperator.STARTS_WITH:
            assert isinstance(value, str)
            return column.startswith(value, autoescape=True)
        if operator is QueryOperator.ENDS_WITH:
            assert isinstance(value, str)
            return column.endswith(value, autoescape=True)
        raise AssertionError(operator)

    def _ordering(
        self,
        model: Any,
        entity_kind: str,
        schema: QuerySchema,
        ordering: tuple[SortExpression, ...],
    ) -> tuple[Any, ...]:
        rules = ordering or (SortExpression("created_at"),)
        clauses: list[Any] = []
        for rule in rules:
            field = schema.field(rule.field)
            if field.key == "tag":
                raise ValidationError(
                    "tag collection cannot be used as an ordering field",
                    code="segment.query.ordering.invalid_field",
                    context={"field": field.key},
                )
            if field.key.startswith("custom."):
                definition = self._custom_definition(
                    entity_kind,
                    field.key.split(".", 1)[1],
                )
                if definition is None:
                    raise ValidationError(
                        "query field is not available for entity kind",
                        code="segment.query.invalid_field",
                        context={
                            "entity_kind": entity_kind,
                            "field": field.key,
                        },
                    )
                raw = CustomFieldValueModel.value_json["value"]
                scalar = self._custom_scalar(raw, field)
                column = (
                    select(self._normalized_sql_value(scalar, field))
                    .where(
                        CustomFieldValueModel.definition_id
                        == str(definition.id),
                        CustomFieldValueModel.entity_kind == entity_kind,
                        CustomFieldValueModel.entity_id == model.id,
                    )
                    .limit(1)
                    .scalar_subquery()
                )
            else:
                column = self._normalized_sql_value(
                    self._base_column(model, field.key),
                    field,
                )
            clause = (
                column.asc()
                if rule.direction is SortDirection.ASC
                else column.desc()
            )
            clause = (
                clause.nulls_first()
                if rule.null_order is NullOrder.FIRST
                else clause.nulls_last()
            )
            clauses.append(clause)
        clauses.append(model.id.asc())
        return tuple(clauses)


__all__ = ["SQLAlchemySegmentQueryExecutor"]
