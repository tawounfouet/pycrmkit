# Saved Queries

> Introduced in PyCRMKit **1.1.0a2**.

A `SavedQuery` stores reusable CRM selection semantics without owning members.

~~~text
SavedQuery
├── stable ID/key
├── entity kind
├── QueryExpression
├── deterministic ordering
├── visibility
├── owner
├── revision
└── metadata
~~~

It is distinct from a Segment:

~~~text
SavedQuery = reusable selection
Segment    = named CRM population

Dynamic Segment
    may bind to one exact SavedQuery revision
~~~

## Create and execute

~~~python
from pycrmkit import CRM
from pycrmkit.segments import Predicate, QueryOperator, SortDirection, SortExpression

crm = CRM.memory()

query = crm.saved_queries.create(
    key="active-linkedin",
    name="Active LinkedIn Contacts",
    entity_kind="contact",
    expression=Predicate("source", QueryOperator.EQ, "linkedin"),
    ordering=(SortExpression("display_name", SortDirection.ASC),),
)

members = crm.saved_queries.execute(query.id)
~~~

## Versioned updates

Updating a SavedQuery creates a new revision with the same stable ID/key.

~~~python
from pycrmkit.saved_queries import SavedQueryRevision

updated = crm.saved_queries.update(
    query.id,
    SavedQueryRevision(name="LinkedIn Contacts"),
    expected_revision=query.revision,
)
~~~

A stale revision fails with `saved_query.revision.conflict`.

## Dynamic Segment binding

~~~python
segment = crm.segments.create_dynamic_from_saved_query(
    key="campaign-audience",
    name="Campaign Audience",
    saved_query_id=query.id,
)
~~~

The Segment copies the expression and records `saved_query_id` plus `saved_query_revision`.
Later SavedQuery edits do not silently change the Segment.

## Custom Fields

Supported scalar Custom Fields use:

~~~text
custom.<field_key>
~~~

Example:

~~~python
Predicate("custom.annual_budget", QueryOperator.GTE, Decimal("100000"))
~~~

Supported portable scalar families in this alpha are string/text, integer, decimal,
boolean, date, datetime, email, phone, URL and enum.

## Tags

Tags use the virtual query field `tag`:

~~~python
Predicate("tag", QueryOperator.EQ, "vip")
Predicate("tag", QueryOperator.IN, ("vip", "enterprise"))
~~~

## Relative time

Moving windows use the injected PyCRMKit `Clock`:

~~~python
from pycrmkit.segments import RelativeTimeUnit, RelativeTimeValue

Predicate(
    "created_at",
    QueryOperator.GTE,
    RelativeTimeValue(-30, RelativeTimeUnit.DAYS),
)
~~~

Supported units are minutes, hours, days and weeks.

## Ordering

Saved Queries store deterministic ordering:

~~~python
SortExpression("display_name", direction=SortDirection.ASC)
~~~

A stable entity ID is used as final tie-breaker.

## Persistence status

From **1.1.0b1**, SavedQuery revision history is persisted by the official
SQLAlchemy/PostgreSQL adapter.

Each revision is immutable and stored under the composite identity:

~~~text
(saved_query_id, revision)
~~~

The adapter preserves exact expression serialization, ordering rules, visibility,
archive state and revision history. Dynamic Segments keep the same exact-revision
binding semantics across Memory and SQLAlchemy.

From **1.1.0b2**, the Django adapter also persists SavedQuery revision history
and executes portable Contact/Organization queries through the Django ORM.

The current Django bridge intentionally rejects fields whose backing state is
not yet owned by that adapter, including Tag and Custom Field predicates.
