# Segmentation Repository Contracts

PyCRMKit 1.1.0a1 separates Segment definition persistence, stored membership and dynamic evaluation.

~~~text
SegmentService
├── SegmentRepository
├── SegmentMembershipRepository
└── SegmentQueryExecutor
~~~

## SegmentRepository

Responsibilities:

~~~text
get
find
find_by_key
save
search
~~~

The repository owns persistence only. It does not decide Dynamic membership.

## SegmentMembershipRepository

Responsibilities:

~~~text
add
remove
contains
list
count
~~~

It stores only explicit memberships such as Static Segments. Dynamic membership is derived through `SegmentQueryExecutor`.

## SegmentQueryExecutor

Responsibilities:

~~~text
execute
count
exists
~~~

The executor consumes the same portable `QueryExpression` contract regardless of backend.

The Memory implementation is the 1.1.0a1 semantic reference. SQLAlchemy/PostgreSQL compilation is intentionally deferred to 1.1.0b1.

## Unit of Work capability

Segmentation uses a dedicated runtime-checkable `SegmentUnitOfWork` capability:

~~~text
segments
segment_memberships
segment_query_executor
~~~

This lets 1.1.0a1 add the Memory implementation without falsely claiming that existing SQLAlchemy/Django Unit-of-Work adapters already persist Segments.

Unsupported adapters fail explicitly rather than silently falling back to in-memory behavior.
