"""Stable enums for CRM segmentation."""

from enum import StrEnum


class SegmentMode(StrEnum):
    """Membership strategy for a Segment."""

    STATIC = "static"
    DYNAMIC = "dynamic"
    SNAPSHOT = "snapshot"


class SegmentStatus(StrEnum):
    """Lifecycle state for a Segment definition."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class QueryOperator(StrEnum):
    """Portable operators supported by the query-expression language."""

    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"


class QueryFieldType(StrEnum):
    """Portable field types shared by all query adapters."""

    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    ID = "id"


__all__ = [
    "QueryFieldType",
    "QueryOperator",
    "SegmentMode",
    "SegmentStatus",
]
