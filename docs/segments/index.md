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

Snapshot Segments are part of the public vocabulary but their creation/persistence is deliberately deferred to the later 1.1 milestone.

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

## Persistence status in 1.1.0a1

The Memory adapter is the semantic reference implementation.

SQLAlchemy/PostgreSQL and Django Segmentation persistence are intentionally not included in this alpha. Calling `crm.segments` with an adapter that does not yet implement the Segmentation capability raises:

~~~text
segment.persistence.unsupported
~~~

Those adapters are delivered by later 1.1 beta milestones.

## Next milestone

`1.1.0a2` adds:

- Saved Queries;
- Custom Field filters;
- Tag filters;
- relative-time expressions;
- reusable query revisions.
