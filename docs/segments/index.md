# Segmentation

> Introduced in PyCRMKit **1.1.0a1**.

Segmentation provides a first-class, headless CRM population model.

The initial alpha supports:

- **Static Segments** with explicit stored memberships;
- **Dynamic Segments** evaluated from a portable query-expression AST;
- Contact, Organization, Lead and Opportunity populations;
- deterministic Memory evaluation;
- bounded pagination and query complexity;
- versioned expression serialization.

Snapshot Segments are fully materialized from **1.1.0b2**. They freeze one
population into immutable stored membership and are supported by Memory,
SQLAlchemy/PostgreSQL and the Django Segmentation adapter.

## Static Segment

~~~python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(
    display_name="Ada Lovelace",
    source="LinkedIn",
)

segment = crm.segments.create_static(
    key="strategic-prospects",
    name="Strategic Prospects",
    entity_kind="contact",
)

crm.segments.add_member(
    segment.id,
    EntityReference("contact", contact.id),
)

assert crm.segments.count(segment.id) == 1
~~~

Static membership is explicit CRM state and can be added/removed through the Segment service.

## Dynamic Segment

~~~python
from pycrmkit.segments import And, Predicate, QueryOperator

segment = crm.segments.create_dynamic(
    key="active-linkedin-prospects",
    name="Active LinkedIn Prospects",
    entity_kind="contact",
    query=And(
        (
            Predicate("status", QueryOperator.EQ, "active"),
            Predicate("source", QueryOperator.EQ, "linkedin"),
        )
    ),
)

members = crm.segments.evaluate(segment.id)
~~~

Dynamic membership is derived and cannot be manually edited.

## Portable expressions

The initial AST is deliberately small:

~~~text
QueryExpression
├── Predicate(field, operator, value)
├── And(expressions)
├── Or(expressions)
└── Not(expression)
~~~

Supported initial operators:

~~~text
eq
ne
lt
lte
gt
gte
in
not_in
is_null
is_not_null
contains
starts_with
ends_with
~~~

Expressions are data, not Python callables. They can therefore be validated, serialized and later compiled by database adapters.

## Typed values

The query schema validates:

~~~text
string
integer
Decimal
boolean
date
timezone-aware datetime
enum
UUID-backed ID
~~~

Binary floating-point literals are rejected for portable financial comparisons.

## Explicit null semantics

Use:

~~~python
Predicate("source", QueryOperator.IS_NULL)
Predicate("source", QueryOperator.IS_NOT_NULL)
~~~

Do not use:

~~~python
Predicate("source", QueryOperator.EQ, None)
~~~

## Persistence status in 1.1.0b1

Memory remains the semantic reference implementation, and **SQLAlchemy/PostgreSQL
is now an official Segmentation adapter**.

The SQLAlchemy capability persists:

~~~text
Segment
SegmentMember
SavedQuery revisions
~~~

and compiles the portable query AST into database-side predicates for:

~~~text
Contact
Organization
Lead
Opportunity
Tags
supported scalar Custom Fields
relative-time expressions
deterministic ordering
~~~

The same `crm.segments` and `crm.saved_queries` facade is used with Memory or
SQLAlchemy; domain code does not receive SQLAlchemy expressions or ORM models.

Migration `0005` creates:

~~~text
pycrmkit_segments
pycrmkit_segment_members
pycrmkit_saved_queries
~~~

Django Segmentation persistence and Snapshot creation remain scheduled for
`1.1.0b2`.


## Snapshot Segment — 1.1.0b2

Freeze a query result:

~~~python
snapshot = crm.segments.create_snapshot(
    key="linkedin-2026-09-29",
    name="LinkedIn 2026-09-29",
    entity_kind="contact",
    expression=Predicate(
        "source",
        QueryOperator.EQ,
        "linkedin",
    ),
)
~~~

Or freeze the current membership of an existing Segment:

~~~python
snapshot = crm.segments.snapshot(
    live_segment.id,
    key="campaign-wave-1",
    name="Campaign Wave 1",
)
~~~

Snapshot membership is immutable. Later CRM changes may change a Dynamic
Segment, but never rewrite the captured Snapshot.

## Bulk membership — 1.1.0b2

Static Segments support bounded transactional membership batches:

~~~python
crm.segments.add_members(
    segment.id,
    (
        EntityReference("contact", contact_a.id),
        EntityReference("contact", contact_b.id),
    ),
)

crm.segments.remove_members(
    segment.id,
    (EntityReference("contact", contact_a.id),),
)
~~~

One batch may contain at most 1000 references. Duplicate references in one add
batch are rejected before persistence.

## Django persistence — 1.1.0b2

The Django bridge now implements Segment, SegmentMember and SavedQuery
persistence plus portable query evaluation for the entity kinds currently owned
by the Django adapter:

~~~text
Contact
Organization
~~~

Django does not silently emulate missing Tag, Custom Field, Lead or Opportunity
state. Queries requiring state not owned by the current Django persistence
bridge fail explicitly.
