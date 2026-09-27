# 04 — Organizations

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Organizations represent the company/account side of the CRM model. This chapter
covers the Organization aggregate, legal and trading identity, DNS domains,
postal addresses, lifecycle, typed updates, search and repository semantics.

## What you will build

By the end of this chapter you will be able to model:

~~~text
Organization
├── legal identity
│   ├── legal_name
│   ├── registration_number
│   └── tax_id
│
├── commercial identity
│   ├── trading_name
│   └── display_name
│
├── digital identity
│   └── domains
│
├── postal identity
│   └── addresses
│
├── CRM ownership
│   ├── owner_id
│   ├── source
│   └── metadata
│
└── lifecycle
    ├── active
    ├── inactive
    └── archived
~~~

The stable application-facing surface is:

~~~text
crm.organizations.create(...)
crm.organizations.get(...)
crm.organizations.update(...)
crm.organizations.search(...)
crm.organizations.archive(...)
~~~

## 1. Organization as an aggregate

An Organization is a Timestamped Entity with a strongly typed OrganizationId.

Its required identity is simpler than Contact:

~~~text
legal_name
    ↓
required
~~~

A valid Organization always has a non-blank legal name.

Additional fields enrich that identity:

~~~text
trading_name
display_name
registration_number
tax_id
domains
addresses
owner_id
source
metadata
~~~

## 2. Create a minimal Organization

~~~python
from pycrmkit import CRM

crm = CRM.memory()

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

print(organization.id)
print(organization.display_name)
~~~

Because no trading/custom display name was provided:

~~~text
display_name = legal_name
~~~

The ID is an OrganizationId, not a raw string.

## 3. Legal name is required

This is invalid:

~~~python
crm.organizations.create(
    legal_name="   ",
)
~~~

PyCRMKit normalizes whitespace first, then raises:

~~~text
ValidationError
code = organization.legal_name.required
~~~

The Organization aggregate therefore cannot exist without a stable legal
identity.

## 4. Legal, trading and display names

PyCRMKit distinguishes three concepts:

~~~text
legal_name
= registered/legal identity

trading_name
= commercial/brand identity

display_name
= CRM-facing presentation identity
~~~

Display-name precedence is deterministic:

~~~text
explicit display_name
        ↓
trading_name
        ↓
legal_name
~~~

Example:

~~~python
organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    trading_name="Example CRM",
)

assert organization.display_name == "Example CRM"
~~~

With an explicit display name:

~~~python
organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    trading_name="Example CRM",
    display_name="Example Enterprise",
)

assert organization.display_name == "Example Enterprise"
~~~

## 5. Registration number and tax ID

The aggregate may carry:

~~~text
registration_number
tax_id
~~~

Example:

~~~python
organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    registration_number="123 456 789",
    tax_id="FR00123456789",
)
~~~

PyCRMKit normalizes surrounding/internal whitespace but deliberately does not
hard-code country-specific company-number or tax-number semantics in the generic
Organization domain.

Country/regulator-specific validation belongs to a higher application layer when
needed.

## 6. Organization domains

Use OrganizationDomain:

~~~python
from pycrmkit.organizations import OrganizationDomain

domain = OrganizationDomain(
    "Example.COM.",
    is_primary=True,
)

print(domain.value)
print(domain.normalized)
~~~

The presentation value is cleaned while comparison uses normalized DNS form.

For the example above:

~~~text
value       = Example.COM
normalized  = example.com
~~~

## 7. Domain validation is intentionally strict

OrganizationDomain accepts a **bare DNS domain**, not a URL or email address.

Valid:

~~~text
example.com
crm.example.com
münich.example
~~~

Invalid:

~~~text
https://example.com
example.com/path
admin@example.com
localhost
~~~

The normalization pipeline includes:

~~~text
trim / Unicode normalization
        ↓
remove trailing dot
        ↓
IDNA encoding
        ↓
case-fold
        ↓
DNS label validation
~~~

Internationalized labels are therefore stored with stable comparison semantics.

## 8. Primary and duplicate domains

An Organization may own several domains:

~~~python
organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    domains=(
        OrganizationDomain(
            "example.com",
            is_primary=True,
        ),
        OrganizationDomain(
            "example.org",
        ),
    ),
)
~~~

But it cannot have more than one primary domain.

This is invalid:

~~~python
crm.organizations.create(
    legal_name="Example Holdings SAS",
    domains=(
        OrganizationDomain("example.com", is_primary=True),
        OrganizationDomain("example.org", is_primary=True),
    ),
)
~~~

and raises:

~~~text
ValidationError
code = organization.domain.multiple_primary
~~~

Duplicate normalized domains are also rejected:

~~~text
Example.COM
example.com.
      ↓
same normalized domain
      ↓
ConflictError
organization.domain.duplicate
~~~

This uniqueness rule applies within one Organization aggregate.

Cross-organization entity resolution/deduplication is a separate concern.

## 9. Organization addresses

Use OrganizationAddress:

~~~python
from pycrmkit.organizations import OrganizationAddress

address = OrganizationAddress(
    line1="10 Downing Street",
    city="London",
    postal_code="SW1A 2AA",
    country_code="gb",
    is_primary=True,
)

assert address.country_code == "GB"
print(address.formatted)
~~~

Required:

~~~text
line1
city
~~~

Optional:

~~~text
line2
postal_code
region
country_code
~~~

When present, country_code must be a two-letter alphabetic ISO-style code and is
normalized to uppercase.

An Organization may have multiple addresses but at most one may be primary.

## 10. Build a complete Organization

~~~python
from pycrmkit import CRM
from pycrmkit.organizations import (
    OrganizationAddress,
    OrganizationDomain,
)

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="organizations-guide-001",
)

organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    trading_name="Example CRM",
    registration_number="123 456 789",
    tax_id="FR00123456789",
    domains=(
        OrganizationDomain(
            "example.com",
            is_primary=True,
        ),
    ),
    addresses=(
        OrganizationAddress(
            line1="10 avenue des Entreprises",
            city="Paris",
            postal_code="75008",
            country_code="FR",
            is_primary=True,
        ),
    ),
    source="zero-to-hero",
    metadata={
        "segment": "enterprise",
        "employees": 250,
    },
)
~~~

Through the CRM facade, this operation:

1. opens a Unit of Work;
2. invokes OrganizationService;
3. validates/normalizes the Organization;
4. saves it through OrganizationRepository;
5. records `organization.created`;
6. commits the transaction.

## 11. Read an Organization

~~~python
reloaded = crm.organizations.get(organization.id)

assert reloaded == organization
~~~

The repository extension contract distinguishes:

~~~text
get(id)
→ Organization
→ or NotFoundError

find(id)
→ Organization | None
~~~

The application-facing facade exposes `get`.

## 12. Typed partial updates

Use OrganizationUpdate:

~~~python
from pycrmkit.organizations import OrganizationUpdate

updated = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        trading_name="Example Cloud",
        source="customer-success",
    ),
)
~~~

As with Contacts, the DTO distinguishes:

~~~text
UNSET
→ keep current value

None
→ explicitly clear a nullable value
~~~

For example:

~~~python
updated = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        trading_name=None,
        tax_id=None,
    ),
)
~~~

clears those values.

## 13. Derived display-name updates

Suppose the Organization starts as:

~~~text
legal_name   = Example Holdings SAS
trading_name = Example CRM
display_name = Example CRM
~~~

If you update the trading name:

~~~python
updated = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        trading_name="Example Cloud",
    ),
)
~~~

the derived display name follows:

~~~text
display_name = Example Cloud
~~~

If the Organization had an explicit custom display name, PyCRMKit preserves it
unless you explicitly update or clear display_name.

## 14. Legal-name updates

Legal name is required even during updates.

You may replace it:

~~~python
updated = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        legal_name="Example Holdings Europe SAS",
    ),
)
~~~

but a blank legal name will fail domain validation.

Unlike optional fields, legal_name cannot be explicitly set to None through the
typed OrganizationUpdate contract.

## 15. Replace domains explicitly

OrganizationUpdate treats collection fields as resulting aggregate state.

Example:

~~~python
updated = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        domains=(
            OrganizationDomain(
                "example.eu",
                is_primary=True,
            ),
            OrganizationDomain(
                "example.com",
            ),
        ),
    ),
)
~~~

This replaces the domain tuple.

It is not an implicit "add one domain" operation.

The same explicit replacement model applies to addresses.

## 16. Lifecycle status

OrganizationStatus defines:

~~~text
ACTIVE
INACTIVE
ARCHIVED
~~~

An Organization is active by default.

It may be created inactive:

~~~python
from pycrmkit.organizations import OrganizationStatus

organization = crm.organizations.create(
    legal_name="Dormant Holdings Ltd",
    status=OrganizationStatus.INACTIVE,
)
~~~

Active/inactive transitions can be represented through OrganizationUpdate.

Archival is deliberately separate.

## 17. Archive through the dedicated operation

Correct:

~~~python
archived = crm.organizations.archive(
    organization.id,
)
~~~

Incorrect:

~~~python
crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        status=OrganizationStatus.ARCHIVED,
    ),
)
~~~

The second form raises InvalidStateError with:

~~~text
organization.update.archive_requires_archive_operation
~~~

The dedicated archive operation sets:

~~~text
status      = archived
archived_at = domain clock timestamp
updated_at  = same timestamp
~~~

Archival is idempotent at the domain/repository contract level.

## 18. Archived Organizations are immutable

Normal updates after archival are rejected:

~~~python
crm.organizations.update(
    archived.id,
    OrganizationUpdate(
        trading_name="Changed",
    ),
)
~~~

raises:

~~~text
InvalidStateError
code = organization.archived
~~~

## 19. Search Organizations

Use OrganizationQuery:

~~~python
from pycrmkit.organizations import OrganizationQuery

page = crm.organizations.search(
    OrganizationQuery(
        name="Example",
    ),
)
~~~

Available stable filters:

~~~text
status
domain
name
registration_number
owner_id
source
include_archived
~~~

These are backend-neutral semantics.

## 20. Search by domain

~~~python
page = crm.organizations.search(
    OrganizationQuery(
        domain="EXAMPLE.COM.",
    ),
)
~~~

OrganizationQuery normalizes the domain first.

That means application code searches using domain semantics instead of
backend-specific comparison logic.

## 21. Search by name

Name search considers:

~~~text
legal_name
trading_name
display_name
~~~

Example:

~~~python
page = crm.organizations.search(
    OrganizationQuery(
        name="cloud",
    ),
)
~~~

can match an Organization whose trading/display name contains `Example Cloud`.

The Memory implementation uses case-insensitive contains semantics, and
persistent adapters are qualified against the shared repository contract.

## 22. Search by registration number

~~~python
page = crm.organizations.search(
    OrganizationQuery(
        registration_number="123 456 789",
    ),
)
~~~

This is a normalized exact semantic filter, case-insensitive where relevant.

PyCRMKit does not attempt country-specific canonicalization of registration
numbers in the generic Organization domain.

## 23. Search by source

~~~python
organization = crm.organizations.create(
    legal_name="Inbound Example Ltd",
    source="website",
)

page = crm.organizations.search(
    OrganizationQuery(
        source="WEBSITE",
    ),
)
~~~

Source equality is case-insensitive in the stable repository semantics.

## 24. Pagination

Search returns Page[Organization].

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.organizations.search(
    OrganizationQuery(),
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)

print(page.items)
print(page.total)
print(page.has_next)
print(page.has_previous)
~~~

The shared stable bounds are:

~~~text
default limit = 50
maximum limit = 200
offset        = non-negative integer
~~~

Repository adapters must use deterministic ordering:

~~~text
created_at ASC
id ASC
~~~

and return exact totals.

## 25. Archived Organizations and search

Archived Organizations are hidden by default:

~~~python
crm.organizations.archive(organization.id)

assert crm.organizations.search().total == 0
~~~

Include them explicitly:

~~~python
page = crm.organizations.search(
    OrganizationQuery(
        include_archived=True,
    ),
)
~~~

Or select only archived records:

~~~python
page = crm.organizations.search(
    OrganizationQuery(
        status=OrganizationStatus.ARCHIVED,
        include_archived=True,
    ),
)
~~~

## 26. Error model

Common Organization errors include:

| Error | Typical Organization case |
| --- | --- |
| ValidationError | blank legal name, invalid domain/address, multiple primaries |
| ConflictError | duplicate normalized domain inside one Organization |
| NotFoundError | get/update/archive unknown OrganizationId |
| InvalidStateError | direct archived creation, archive through update, post-archive mutation |

Every PyCRMKit error exposes:

~~~text
message
code
context
~~~

plus `as_dict()` for transport/error adapters.

Example:

~~~python
from pycrmkit.exceptions import ValidationError

try:
    crm.organizations.create(
        legal_name=" ",
    )
except ValidationError as exc:
    print(exc.code)
    print(exc.as_dict())
~~~

## 27. Events and audit

Organization facade mutations record domain changes such as:

~~~text
organization.created
organization.updated
organization.archived
~~~

With context:

~~~python
crm = CRM.memory().with_context(
    actor_id="account-manager-7",
    correlation_id="organization-onboarding-001",
)

organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
)
~~~

the event/audit infrastructure can correlate the mutation with the broader
business flow.

## 28. Repository extension contract

Most application code should use:

~~~text
crm.organizations
~~~

Adapter authors implement OrganizationRepository:

~~~text
get(OrganizationId) -> Organization
find(OrganizationId) -> Organization | None
save(Organization) -> None
archive(OrganizationId, datetime) -> Organization
search(OrganizationQuery, OffsetPageRequest) -> Page[Organization]
~~~

As with all V1 repositories:

~~~text
save()
≠ commit()
~~~

The outer Unit of Work owns commit/rollback so Organization changes can
participate in larger atomic workflows.

## 29. Complete Organization example

~~~python
from pycrmkit import CRM
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.organizations import (
    OrganizationAddress,
    OrganizationDomain,
    OrganizationQuery,
    OrganizationUpdate,
)

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="organizations-guide-001",
)

organization = crm.organizations.create(
    legal_name="Example Holdings SAS",
    trading_name="Example CRM",
    registration_number="123 456 789",
    domains=(
        OrganizationDomain(
            "Example.COM.",
            is_primary=True,
        ),
    ),
    addresses=(
        OrganizationAddress(
            line1="10 avenue des Entreprises",
            city="Paris",
            postal_code="75008",
            country_code="fr",
            is_primary=True,
        ),
    ),
    source="zero-to-hero",
)

assert organization.display_name == "Example CRM"
assert organization.domains[0].normalized == "example.com"
assert organization.addresses[0].country_code == "FR"

organization = crm.organizations.update(
    organization.id,
    OrganizationUpdate(
        trading_name="Example Cloud",
        source=None,
    ),
)

assert organization.display_name == "Example Cloud"
assert organization.source is None

page = crm.organizations.search(
    OrganizationQuery(
        domain="EXAMPLE.COM.",
    ),
    OffsetPageRequest(
        limit=10,
    ),
)

assert page.total == 1
assert page.items[0].id == organization.id

archived = crm.organizations.archive(
    organization.id,
)

assert archived.status.value == "archived"
assert crm.organizations.search().total == 0

with_archived = crm.organizations.search(
    OrganizationQuery(
        include_archived=True,
    ),
)

assert with_archived.total == 1
~~~

## 30. What happens internally?

A facade mutation follows:

~~~text
Application
    ↓
crm.organizations
    ↓
OrganizationsAPI
    ↓
Unit of Work
    ↓
OrganizationService
    ↓
Organization validation / normalization
    ↓
OrganizationRepository
    ↓
event + audit staging
    ↓
commit
~~~

The same domain language survives when Memory is replaced by the
SQLAlchemy/PostgreSQL or Django adapter.

## Common mistakes

### Treating trading_name as legal_name

They represent different business concepts. Keep the registered legal identity
separate from the brand/commercial identity.

### Storing website URLs as OrganizationDomain

Use bare DNS names. `https://example.com` is intentionally rejected.

### Expecting PyCRMKit to guess jurisdiction-specific tax/registration rules

The generic Organization domain preserves normalized text but does not encode
every national registry format.

### Mutating domain/address tuples in place

Use OrganizationUpdate and provide the resulting tuple explicitly.

### Archiving through OrganizationUpdate

Use the dedicated `crm.organizations.archive(...)` operation.

### Querying ORM models directly

Use OrganizationQuery at the application boundary to preserve adapter parity.

## Testing Organization workflows

Application tests should verify observable stable behavior:

~~~python
from pycrmkit import CRM
from pycrmkit.organizations import (
    OrganizationDomain,
    OrganizationQuery,
)

def test_organization_can_be_found_by_domain() -> None:
    crm = CRM.memory()

    organization = crm.organizations.create(
        legal_name="Example Holdings SAS",
        domains=(
            OrganizationDomain(
                "example.com",
                is_primary=True,
            ),
        ),
    )

    page = crm.organizations.search(
        OrganizationQuery(
            domain="EXAMPLE.COM",
        ),
    )

    assert [item.id for item in page.items] == [organization.id]
~~~

Repository-contract and PostgreSQL tests then prove that persistent adapters
preserve the same observable semantics.

## What you learned

You can now explain and use:

- Organization and OrganizationId;
- required legal identity;
- legal/trading/display-name semantics;
- registration_number and tax_id;
- OrganizationDomain and IDNA/DNS normalization;
- primary and duplicate domain rules;
- OrganizationAddress;
- OrganizationUpdate and UNSET semantics;
- active/inactive/archive lifecycle;
- archive immutability;
- OrganizationQuery;
- domain/name/registration/source filters;
- deterministic pagination;
- archived-search behavior;
- OrganizationRepository and Unit of Work boundaries.

## Next

The next planned chapter is **05 — Relationships**.

That chapter connects the two aggregates you now understand:

~~~text
Contact
   ↓
Relationship
   ↓
Organization
~~~

and introduces directional endpoints, open-ended relationship types, roles,
primary relationships and lifecycle semantics.
