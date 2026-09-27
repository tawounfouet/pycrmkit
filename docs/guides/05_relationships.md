# 05 — Relationships

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Relationships turn isolated CRM records into a graph. They connect Contacts and
Organizations with explicit direction, typed endpoints, semantic relationship
types, roles and validity intervals.

## What you will build

By the end of this chapter you will be able to model:

~~~text
Contact
   │
   │ source
   ▼
Relationship
   │
   │ target
   ▼
Organization
~~~

and also:

~~~text
Contact → Contact
Organization → Organization
~~~

The stable application-facing surface is:

~~~text
crm.relationships.create(...)
crm.relationships.get(...)
crm.relationships.update(...)
crm.relationships.search(...)
crm.relationships.end(...)
~~~

## 1. Why Relationships are separate aggregates

Do not hide company membership or other links inside Contact or Organization
fields.

Instead of:

~~~text
Contact.company_id
~~~

PyCRMKit models:

~~~text
Contact
   ↓
Relationship
   ↓
Organization
~~~

This makes the link itself a first-class CRM object with its own:

~~~text
type
role
title
primary flag
validity
metadata
history
~~~

That is essential for real CRM graphs where one person may have several
organizations, roles or historical affiliations.

## 2. Relationship identity

A Relationship is a Timestamped Entity with a RelationshipId.

Its essential shape is:

~~~text
Relationship
├── source
├── target
├── relationship_type
├── role
├── title
├── is_primary
├── valid_from
├── valid_until
└── metadata
~~~

A Relationship is directional:

~~~text
source → target
~~~

Direction is part of its meaning.

## 3. Typed endpoints

RelationshipEndpoint represents one participant without hydrating that entity.

Use the constructors:

~~~python
from pycrmkit.relationships import RelationshipEndpoint

contact_endpoint = RelationshipEndpoint.contact(contact.id)
organization_endpoint = RelationshipEndpoint.organization(organization.id)
~~~

The endpoint stores:

~~~text
kind + typed ID
~~~

For example:

~~~text
contact      + ContactId
organization + OrganizationId
~~~

PyCRMKit rejects a mismatched pair such as an OrganizationId inside a contact
endpoint.

## 4. Supported participant shapes

The V1 relationship domain supports:

~~~text
Contact      → Organization
Contact      → Contact
Organization → Organization
Organization → Contact
~~~

The type system does not force one particular CRM interpretation. Meaning comes
from direction plus RelationshipType, role/title and application conventions.

## 5. Create your first Relationship

~~~python
from pycrmkit import CRM
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipType,
)

crm = CRM.memory()

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    role="founder",
    is_primary=True,
)
~~~

The relationship now expresses:

~~~text
Ada Lovelace
     │
 employment
 role=founder
     │
     ▼
Analytical Engines Ltd
~~~

## 6. RelationshipType is open-ended

RelationshipType is not a closed enum.

You can create domain-specific relationship codes:

~~~python
RelationshipType("employment")
RelationshipType("board member")
RelationshipType("subsidiary")
RelationshipType("partner_org")
~~~

Normalization produces stable lowercase semantic codes:

~~~text
"Board Member" → "board-member"
"partner_org"  → "partner-org"
~~~

Whitespace and underscores become hyphens.

The code cannot be blank and cannot exceed 80 characters.

## 7. Direction matters

These are not automatically equivalent:

~~~text
Contact → Organization
Organization → Contact
~~~

The repository can filter by source and target separately.

For example, this relationship:

~~~python
relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
)
~~~

has:

~~~text
source.kind = contact
target.kind = organization
~~~

If your application needs inverse semantics, model or query them explicitly.

## 8. Self-links are forbidden

A Relationship cannot connect an entity to itself.

This is invalid:

~~~python
endpoint = RelationshipEndpoint.contact(contact.id)

crm.relationships.create(
    source=endpoint,
    target=endpoint,
    relationship_type=RelationshipType("peer"),
)
~~~

and raises:

~~~text
ConflictError
code = relationship.self_link
~~~

Different Contacts may still be linked to each other, and different
Organizations may be linked to each other.

## 9. Role and title

RelationshipType answers:

~~~text
What kind of relationship is this?
~~~

role and title provide human/business context.

Example:

~~~python
relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    role="customer-success",
    title="Account Manager",
)
~~~

A useful mental model is:

~~~text
relationship_type = semantic category
role              = function in the relationship
title             = human-readable position/title
~~~

Both role and title are optional normalized text.

## 10. Primary Relationship

is_primary marks a relationship as primary for application semantics:

~~~python
relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    is_primary=True,
)
~~~

Unlike primary email/domain rules, the Relationship aggregate itself does not
enforce a global "only one primary relationship per entity" invariant.

That kind of cross-record policy belongs at a higher application/business layer
if your CRM needs it.

## 11. Validity starts at valid_from

Every Relationship has a valid_from timestamp.

If you omit it:

~~~python
relationship = crm.relationships.create(
    source=source,
    target=target,
    relationship_type=RelationshipType("employment"),
)
~~~

PyCRMKit uses the current domain clock.

You may provide an explicit timestamp when importing historical CRM data.

## 12. Half-open validity interval

Relationship activity uses:

~~~text
valid_from <= instant < valid_until
~~~

This is a half-open interval:

~~~text
[valid_from, valid_until)
~~~

When valid_until is absent, the relationship remains open-ended.

You can test a relationship directly:

~~~python
is_active = relationship.is_active(some_datetime)
~~~

## 13. Invalid validity intervals

valid_until must be strictly later than valid_from.

This is invalid:

~~~text
valid_until <= valid_from
~~~

and raises:

~~~text
ValidationError
code = relationship.validity.invalid_interval
~~~

This prevents zero-length or backwards relationship histories.

## 14. End a Relationship

Use the dedicated lifecycle operation:

~~~python
ended = crm.relationships.end(relationship.id)
~~~

That sets valid_until using the domain clock.

The operation records:

~~~text
relationship.ended
~~~

through the facade.

It does not physically delete the relationship, because historical CRM links are
valuable data.

## 15. Ending is idempotent

At the aggregate/repository level, ending an already ended relationship leaves
its original valid_until unchanged.

That gives stable historical semantics instead of repeatedly moving the end
timestamp.

## 16. Ended Relationships are immutable

After a relationship has ended, normal profile mutation is rejected:

~~~python
crm.relationships.update(
    ended.id,
    RelationshipUpdate(
        title="Changed",
    ),
)
~~~

raises:

~~~text
InvalidStateError
code = relationship.ended
~~~

The historical record is therefore protected.

## 17. Typed partial updates

Use RelationshipUpdate:

~~~python
from pycrmkit.relationships import RelationshipUpdate

updated = crm.relationships.update(
    relationship.id,
    RelationshipUpdate(
        title="Senior Account Manager",
        is_primary=False,
    ),
)
~~~

The DTO supports partial changes to:

~~~text
source
target
relationship_type
role
title
is_primary
valid_from
metadata
~~~

As elsewhere in PyCRMKit:

~~~text
UNSET
→ leave unchanged

None
→ explicitly clear nullable role/title
~~~

valid_until is deliberately not updated through RelationshipUpdate. Use
`end(...)` for lifecycle termination.

## 18. Endpoints may be updated while active

An active relationship can be re-pointed through RelationshipUpdate:

~~~python
updated = crm.relationships.update(
    relationship.id,
    RelationshipUpdate(
        target=RelationshipEndpoint.organization(other_org.id),
    ),
)
~~~

The resulting candidate is fully revalidated, including the self-link rule.

Whether your business process should permit such reassignment is an
application-level policy; the V1 domain contract permits it while active.

## 19. Search Relationships

Use RelationshipQuery:

~~~python
from pycrmkit.relationships import RelationshipQuery

page = crm.relationships.search(
    RelationshipQuery(
        entity=RelationshipEndpoint.contact(contact.id),
    ),
)
~~~

Available filters are:

~~~text
entity
source
target
relationship_type
is_primary
active_at
include_ended
~~~

## 20. Search by entity

entity means:

~~~text
source == entity
OR
target == entity
~~~

This is useful for retrieving the relationship neighborhood of a CRM entity:

~~~python
page = crm.relationships.search(
    RelationshipQuery(
        entity=RelationshipEndpoint.organization(organization.id),
    ),
)
~~~

## 21. Search by source or target

Use directional filters when direction matters:

~~~python
by_source = crm.relationships.search(
    RelationshipQuery(
        source=RelationshipEndpoint.contact(contact.id),
    ),
)

by_target = crm.relationships.search(
    RelationshipQuery(
        target=RelationshipEndpoint.organization(organization.id),
    ),
)
~~~

This preserves source→target semantics explicitly.

## 22. Search by type

~~~python
employment = crm.relationships.search(
    RelationshipQuery(
        relationship_type=RelationshipType("Employment"),
    ),
)
~~~

Because RelationshipType normalizes its code, query and stored relationship use
the same stable semantic representation.

## 23. Search primary relationships

~~~python
primary = crm.relationships.search(
    RelationshipQuery(
        is_primary=True,
    ),
)
~~~

This is a boolean filter only; it does not imply uniqueness across records.

## 24. Ended relationships are hidden by default

After:

~~~python
crm.relationships.end(relationship.id)
~~~

the default search excludes that record:

~~~python
assert crm.relationships.search().total == 0
~~~

To include historical relationships:

~~~python
page = crm.relationships.search(
    RelationshipQuery(
        include_ended=True,
    ),
)
~~~

## 25. Search by active_at

For historical/temporal queries:

~~~python
page = crm.relationships.search(
    RelationshipQuery(
        active_at=some_datetime,
    ),
)
~~~

When active_at is present, repository adapters evaluate the half-open interval:

~~~text
valid_from <= active_at < valid_until
~~~

or treat the relationship as active when valid_until is absent.

active_at therefore provides a temporal snapshot of the relationship graph.

## 26. active_at vs include_ended

These two concepts answer different questions:

~~~text
include_ended=True
→ include historical records regardless of current open/ended state

active_at=T
→ include only relationships active at exact instant T
~~~

When active_at is supplied, activity semantics drive the filtering.

## 27. Pagination

Relationship search returns Page[Relationship].

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.relationships.search(
    RelationshipQuery(
        entity=RelationshipEndpoint.contact(contact.id),
    ),
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)
~~~

Repository adapters provide deterministic ordering:

~~~text
created_at ASC
id ASC
~~~

and exact totals.

## 28. Typed endpoint validation

RelationshipEndpoint protects ID-kind parity.

Conceptually:

~~~text
RelationshipEntityKind.CONTACT
        requires
ContactId

RelationshipEntityKind.ORGANIZATION
        requires
OrganizationId
~~~

This makes a whole class of cross-domain ID mistakes fail at the domain boundary.

Prefer:

~~~python
RelationshipEndpoint.contact(contact.id)
RelationshipEndpoint.organization(organization.id)
~~~

over constructing kind/ID pairs manually.

## 29. Events and operation context

Facade mutations record:

~~~text
relationship.created
relationship.updated
relationship.ended
~~~

Use CRM context for traceability:

~~~python
crm = CRM.memory().with_context(
    actor_id="account-manager-7",
    correlation_id="relationship-onboarding-001",
)
~~~

Then relationship changes participate in the same event/audit flow as Contacts
and Organizations.

## 30. Repository extension contract

Most applications should use:

~~~text
crm.relationships
~~~

Adapter authors implement RelationshipRepository:

~~~text
get(RelationshipId) -> Relationship
find(RelationshipId) -> Relationship | None
save(Relationship) -> None
end(RelationshipId, datetime) -> Relationship
search(RelationshipQuery, OffsetPageRequest) -> Page[Relationship]
~~~

As with other V1 repositories:

~~~text
save()
≠ commit()
~~~

The outer Unit of Work owns transaction commit/rollback.

## 31. Complete Relationship example

~~~python
from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipQuery,
    RelationshipType,
    RelationshipUpdate,
)

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="relationships-guide-001",
)

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

source = RelationshipEndpoint.contact(contact.id)
target = RelationshipEndpoint.organization(organization.id)

relationship = crm.relationships.create(
    source=source,
    target=target,
    relationship_type=RelationshipType("Board Member"),
    role="founder",
    title="Director",
    is_primary=True,
    metadata={"source_system": "manual"},
)

assert str(relationship.relationship_type) == "board-member"
assert relationship.source == source
assert relationship.target == target
assert relationship.is_ended is False

relationship = crm.relationships.update(
    relationship.id,
    RelationshipUpdate(
        title="Executive Director",
        is_primary=False,
    ),
)

assert relationship.title == "Executive Director"
assert relationship.is_primary is False

page = crm.relationships.search(
    RelationshipQuery(
        entity=source,
        relationship_type=RelationshipType("board_member"),
    ),
    OffsetPageRequest(limit=10),
)

assert page.total == 1
assert page.items[0].id == relationship.id

ended = crm.relationships.end(relationship.id)

assert ended.is_ended is True
assert crm.relationships.search().total == 0

history = crm.relationships.search(
    RelationshipQuery(
        include_ended=True,
    ),
)

assert history.total == 1
~~~

## 32. Historical validity example

For imported history, supply explicit validity:

~~~python
start = datetime(2025, 1, 1, tzinfo=UTC)
end = datetime(2026, 1, 1, tzinfo=UTC)

historical = crm.relationships.create(
    source=source,
    target=target,
    relationship_type=RelationshipType("employment"),
    valid_from=start,
    valid_until=end,
)

assert historical.is_active(
    datetime(2025, 6, 1, tzinfo=UTC)
)
assert not historical.is_active(
    datetime(2026, 1, 1, tzinfo=UTC)
)
~~~

Notice the boundary:

~~~text
2025-06-01
inside interval → active

2026-01-01
equal to valid_until → inactive
~~~

## 33. What happens internally?

A mutation follows:

~~~text
Application
    ↓
crm.relationships
    ↓
RelationshipsAPI
    ↓
Unit of Work
    ↓
RelationshipService
    ↓
typed endpoint + validity validation
    ↓
RelationshipRepository
    ↓
event + audit staging
    ↓
commit
~~~

That architecture keeps relationship semantics independent of Memory,
SQLAlchemy/PostgreSQL or Django persistence.

## Common mistakes

### Treating a relationship as an embedded Contact field

You lose role, direction, history, primary semantics and temporal validity.

### Ignoring direction

source and target are not interchangeable. Use entity when direction does not
matter; use source/target filters when it does.

### Using raw strings/UUIDs as endpoints

Use RelationshipEndpoint.contact(...) and
RelationshipEndpoint.organization(...).

### Treating RelationshipType as a fixed enum

It is intentionally open-ended and normalized, allowing domain-specific
relationship vocabularies.

### Deleting ended relationships

Use end(). CRM history should remain queryable.

### Updating valid_until directly

Lifecycle termination belongs to end(), not RelationshipUpdate.

### Assuming is_primary is globally unique

The Relationship aggregate stores the flag but does not enforce cross-record
uniqueness.

## Testing Relationship workflows

Test observable semantics:

~~~python
from pycrmkit import CRM
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipQuery,
    RelationshipType,
)

def test_contact_relationship_can_be_found() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(display_name="Ada Lovelace")
    organization = crm.organizations.create(
        legal_name="Analytical Engines Ltd",
    )

    endpoint = RelationshipEndpoint.contact(contact.id)

    relationship = crm.relationships.create(
        source=endpoint,
        target=RelationshipEndpoint.organization(organization.id),
        relationship_type=RelationshipType("employment"),
    )

    page = crm.relationships.search(
        RelationshipQuery(entity=endpoint),
    )

    assert [item.id for item in page.items] == [relationship.id]
~~~

Persistent adapter contract tests should then prove the same semantics against
PostgreSQL/Django.

## What you learned

You can now explain and use:

- Relationship and RelationshipId;
- source→target direction;
- RelationshipEndpoint typed references;
- Contact/Organization endpoint parity;
- open-ended RelationshipType codes;
- role/title/primary semantics;
- self-link prevention;
- valid_from / valid_until;
- half-open interval semantics;
- dedicated end lifecycle;
- ended-record immutability;
- RelationshipUpdate;
- RelationshipQuery entity/source/target/type/primary filters;
- temporal active_at queries;
- historical include_ended queries;
- deterministic pagination;
- RelationshipRepository and Unit of Work boundaries.

## Next

The next planned chapter is **06 — Tags & Custom Fields**.

That chapter finishes LEVEL 1 by introducing extensible CRM classification and
business-specific data without modifying the Contact, Organization or
Relationship aggregates themselves.
