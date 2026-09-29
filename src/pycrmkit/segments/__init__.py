"""Segmentation domain and portable query-expression model."""

from pycrmkit.segments.data_operations import (
    SegmentDataOperationsAPI,
    SegmentMembershipPersister,
    SegmentMembershipValidator,
    import_segment_members,
    iter_segment_membership_records,
)
from pycrmkit.segments.entities import (
    SEGMENTABLE_ENTITY_KINDS,
    Segment,
    SegmentId,
    SegmentMember,
    normalize_segment_key,
)
from pycrmkit.segments.enums import (
    QueryFieldType,
    QueryOperator,
    SegmentMode,
    SegmentStatus,
)
from pycrmkit.segments.expressions import (
    MAX_EXPRESSION_DEPTH,
    MAX_IN_VALUES,
    MAX_PREDICATES,
    QUERY_EXPRESSION_SCHEMA_VERSION,
    SUPPORTED_QUERY_EXPRESSION_SCHEMA_VERSIONS,
    And,
    Not,
    Or,
    Predicate,
    QueryExpression,
    RelativeTimeUnit,
    RelativeTimeValue,
    expression_from_dict,
    expression_to_dict,
)
from pycrmkit.segments.ordering import NullOrder, SortDirection, SortExpression
from pycrmkit.segments.queries import SegmentQuery
from pycrmkit.segments.repository import (
    SegmentMembershipRepository,
    SegmentQueryExecutor,
    SegmentRepository,
)
from pycrmkit.segments.schema import (
    QueryField,
    QuerySchema,
    QuerySchemaRegistry,
    default_query_schemas,
)
from pycrmkit.segments.services import SegmentService
from pycrmkit.segments.unit_of_work import SegmentUnitOfWork

__all__ = [
    "MAX_EXPRESSION_DEPTH",
    "MAX_IN_VALUES",
    "MAX_PREDICATES",
    "QUERY_EXPRESSION_SCHEMA_VERSION",
    "SUPPORTED_QUERY_EXPRESSION_SCHEMA_VERSIONS",
    "SEGMENTABLE_ENTITY_KINDS",
    "SegmentDataOperationsAPI",
    "SegmentMembershipPersister",
    "SegmentMembershipValidator",
    "And",
    "Not",
    "NullOrder",
    "Or",
    "Predicate",
    "QueryExpression",
    "RelativeTimeUnit",
    "RelativeTimeValue",
    "QueryField",
    "QueryFieldType",
    "QueryOperator",
    "QuerySchema",
    "QuerySchemaRegistry",
    "Segment",
    "SegmentId",
    "SegmentMember",
    "SegmentMembershipRepository",
    "SegmentMode",
    "SegmentQuery",
    "SegmentQueryExecutor",
    "SegmentRepository",
    "SegmentService",
    "SegmentStatus",
    "SegmentUnitOfWork",
    "SortDirection",
    "SortExpression",
    "default_query_schemas",
    "expression_from_dict",
    "expression_to_dict",
    "normalize_segment_key",
]
