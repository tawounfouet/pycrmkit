# Relationships

`0.1.0b1` introduces directional, typed CRM relationships without coupling the domain to an ORM.

## Supported participants

```text
Contact      → Organization
Contact      → Contact
Organization → Organization
```

Participants are represented by `RelationshipEndpoint`, which combines an entity kind with a strongly typed `ContactId` or `OrganizationId`. Repositories therefore do not need to hydrate linked entities merely to represent a relationship.

## Example

```python
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipService,
    RelationshipType,
)

relationship = service.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    role="Customer Success",
    title="Account Manager",
    is_primary=True,
)
```

## Validity

Relationship validity uses a half-open interval:

```text
valid_from <= instant < valid_until
```

When `valid_until` is absent, the relationship remains open-ended. `end()` is idempotent and does not physically delete history.

## Boundaries

This milestone deliberately excludes tags, custom fields, production Memory repositories, SQLAlchemy/Django persistence, and relationship-derived projections.
