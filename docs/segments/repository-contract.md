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
add_many
remove
remove_many
contains
list
count
~~~

It stores only explicit memberships such as Static and Snapshot Segments. Dynamic membership is derived through `SegmentQueryExecutor`.

Bulk operations are bounded and transactional. `add_many` validates the whole
batch before persistence; `remove_many` is idempotent and returns the number of
deleted memberships.

## SegmentQueryExecutor

Responsibilities:

~~~text
execute
count
exists
~~~

The executor consumes the same portable `QueryExpression` contract regardless of backend.

Memory remains the semantic reference. SQLAlchemy/PostgreSQL implements the
same contracts from 1.1.0b1, and Django implements the Contact/Organization
Segmentation capability from 1.1.0b2.

## Unit of Work capability

Segmentation uses a dedicated runtime-checkable `SegmentUnitOfWork` capability:

~~~text
segments
segment_memberships
segment_query_executor
~~~

This lets 1.1.0a1 add the Memory implementation without falsely claiming that existing SQLAlchemy/Django Unit-of-Work adapters already persist Segments.

Unsupported adapters fail explicitly rather than silently falling back to in-memory behavior.


## Snapshot semantics

A Snapshot Segment is immutable stored membership captured from either a
portable query expression or an existing Segment.

~~~text
live population
    ↓ evaluate once at captured_at
Snapshot Segment
    ↓
stored immutable memberships
~~~

Snapshot creation and membership materialization occur in one Unit of Work.
Changing the source Dynamic Segment or underlying CRM records never rewrites the
Snapshot.
