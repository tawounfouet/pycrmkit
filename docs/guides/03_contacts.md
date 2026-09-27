# 03 — Contacts

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Contacts are the first major CRM aggregate in the Zero-to-Hero path. This
chapter goes beyond creating a name: you will learn the Contact lifecycle,
contact-point normalization, typed updates, search/pagination and archival
semantics.

## What you will build

By the end of this chapter you will be able to manage a complete Contact profile:

~~~text
Contact
├── identity
│   ├── first_name
│   ├── last_name
│   └── display_name
│
├── contact points
│   ├── emails
│   ├── phones
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

You will use the stable application-facing facade:

~~~text
crm.contacts.create(...)
crm.contacts.get(...)
crm.contacts.update(...)
crm.contacts.search(...)
crm.contacts.archive(...)
~~~

## 1. Contact as an aggregate

A Contact is a domain Entity with a strongly typed ContactId.

Conceptually:

~~~text
Contact
  ↓
Timestamped Entity
  ↓
ContactId
  ↓
created_at / updated_at
~~~

The aggregate owns the rules that make a Contact valid. Application code should
not treat it as an unvalidated dictionary or database row.

The V1 Contact contains:

~~~text
id
created_at
updated_at

first_name
last_name
display_name

status
owner_id
source

emails
phones
addresses

metadata
archived_at
~~~

## 2. Create a minimal Contact

Start with an isolated CRM:

~~~python
from pycrmkit import CRM

crm = CRM.memory()

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

print(contact.id)
print(contact.display_name)
~~~

Because no explicit display name was supplied, PyCRMKit derives one:

~~~text
Ada + Lovelace
      ↓
Ada Lovelace
~~~

The generated ID is a ContactId rather than a raw UUID/string.

## 3. Contact identity rules

A Contact must have at least one usable identity signal.

At least one of these must exist:

~~~text
first_name
last_name
display_name
email
phone
~~~

So this is invalid:

~~~python
crm.contacts.create()
~~~

and raises a ValidationError with the domain code:

~~~text
contact.identity.required
~~~

An address by itself does not satisfy the Contact identity rule.

## 4. Explicit vs derived display names

If you provide only first/last name:

~~~python
contact = crm.contacts.create(
    first_name="Grace",
    last_name="Hopper",
)
~~~

the display name is derived:

~~~text
Grace Hopper
~~~

You can also provide an explicit CRM-facing name:

~~~python
contact = crm.contacts.create(
    first_name="Grace",
    last_name="Hopper",
    display_name="Rear Admiral Hopper",
)
~~~

The explicit display name wins.

This distinction matters during updates:

~~~text
derived display_name
+ first/last name change
→ PyCRMKit re-derives the display name

explicit/custom display_name
+ first/last name change
→ PyCRMKit preserves the custom display name
~~~

## 5. Emails as Value Objects

Use ContactEmail rather than a raw string:

~~~python
from pycrmkit.contacts import ContactEmail

email = ContactEmail(
    "Ada.Lovelace@Example.COM",
    is_primary=True,
)
~~~

The object preserves a cleaned display value and exposes a normalized comparison
value:

~~~python
print(email.value)
print(email.normalized)
~~~

For this example:

~~~text
value       = Ada.Lovelace@Example.COM
normalized  = ada.lovelace@example.com
~~~

PyCRMKit deliberately performs CRM-safe normalization rather than
provider-specific rewriting.

It does not, for example, assume that dots or plus-address aliases are
equivalent for a particular email provider.

## 6. Multiple emails and primary semantics

A Contact may have multiple emails:

~~~python
contact = crm.contacts.create(
    display_name="Ada Lovelace",
    emails=(
        ContactEmail(
            "ada@example.com",
            is_primary=True,
        ),
        ContactEmail(
            "ada.work@example.org",
        ),
    ),
)
~~~

But a Contact cannot contain more than one primary email.

This is invalid:

~~~python
crm.contacts.create(
    display_name="Ada Lovelace",
    emails=(
        ContactEmail("ada@example.com", is_primary=True),
        ContactEmail("ada@example.org", is_primary=True),
    ),
)
~~~

and raises:

~~~text
ValidationError
code = contact.email.multiple_primary
~~~

Two emails that normalize to the same value are also rejected:

~~~text
Ada@Example.com
ada@example.com
      ↓
same normalized email
      ↓
ConflictError
contact.email.duplicate
~~~

The uniqueness rule shown here is **within one Contact aggregate**. Cross-contact
duplicate detection is a separate Data Operations concern introduced later.

## 7. Phone numbers

Use ContactPhone:

~~~python
from pycrmkit.contacts import ContactPhone

phone = ContactPhone(
    "+33 6 12 34 56 78",
    is_primary=True,
)

print(phone.normalized)
~~~

The normalized value is:

~~~text
+33612345678
~~~

PyCRMKit removes common separators but deliberately does **not** guess a missing
country code.

For example:

~~~text
06 12 34 56 78
~~~

remains a national-looking number rather than being silently rewritten to a
French international number.

The phone rules also enforce:

- digits plus common separators;
- an optional leading `+`;
- a bounded digit count;
- at most one primary phone per Contact;
- no duplicate normalized phone inside one Contact.

## 8. Postal addresses

Use Address:

~~~python
from pycrmkit.contacts import Address

address = Address(
    line1="12 St James's Square",
    city="London",
    postal_code="SW1Y 4LB",
    country_code="GB",
    is_primary=True,
)
~~~

An Address requires:

~~~text
line1
city
~~~

Optional fields include:

~~~text
line2
postal_code
region
country_code
~~~

When supplied, country_code must be a two-letter alphabetic code and is
normalized to uppercase.

You can obtain a compact human-readable representation:

~~~python
print(address.formatted)
~~~

A Contact can carry multiple addresses but at most one may be primary.

## 9. Build a complete Contact profile

Now combine the value objects:

~~~python
from pycrmkit import CRM
from pycrmkit.contacts import (
    Address,
    ContactEmail,
    ContactPhone,
)

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="contacts-guide-001",
)

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
    emails=(
        ContactEmail(
            "ada@example.com",
            is_primary=True,
        ),
    ),
    phones=(
        ContactPhone(
            "+44 20 7946 0958",
            is_primary=True,
        ),
    ),
    addresses=(
        Address(
            line1="12 St James's Square",
            city="London",
            postal_code="SW1Y 4LB",
            country_code="GB",
            is_primary=True,
        ),
    ),
    source="zero-to-hero",
    metadata={
        "segment": "strategic",
        "language": "en",
    },
)
~~~

At this point the facade has:

1. opened a Unit of Work;
2. created the Contact through ContactService;
3. validated/normalized the aggregate;
4. saved it through the ContactRepository;
5. recorded `contact.created`;
6. committed the transaction.

## 10. Read a Contact

Use the typed ContactId:

~~~python
reloaded = crm.contacts.get(contact.id)

assert reloaded == contact
~~~

The repository contract distinguishes:

~~~text
get(id)
→ Contact
→ or NotFoundError

find(id)
→ Contact | None
~~~

The high-level Contacts facade exposes `get`; `find` is part of the
repository extension contract for adapter authors.

## 11. Typed partial updates

PyCRMKit uses ContactUpdate for profile mutations:

~~~python
from pycrmkit.contacts import ContactUpdate

updated = crm.contacts.update(
    contact.id,
    ContactUpdate(
        last_name="Byron",
        source="customer-success",
    ),
)
~~~

Why a DTO instead of many optional keyword arguments?

Because updates need to distinguish:

~~~text
field omitted
≠
field explicitly cleared with None
~~~

PyCRMKit represents that distinction with the public UNSET sentinel.

Conceptually:

~~~text
UNSET
→ keep current value

None
→ explicitly clear a nullable value
~~~

For example:

~~~python
updated = crm.contacts.update(
    contact.id,
    ContactUpdate(
        source=None,
    ),
)
~~~

clears the source.

## 12. Derived display name during updates

Suppose the Contact started as:

~~~python
contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)
~~~

Its display name is derived as:

~~~text
Ada Lovelace
~~~

If you update the last name:

~~~python
contact = crm.contacts.update(
    contact.id,
    ContactUpdate(
        last_name="Byron",
    ),
)
~~~

the derived display name becomes:

~~~text
Ada Byron
~~~

But if the original Contact had an explicit custom display name, PyCRMKit keeps
that custom value unless you explicitly update/clear it.

## 13. Replace contact-point collections explicitly

ContactUpdate operates on aggregate state. To change emails, phones or
addresses, provide the resulting tuple:

~~~python
contact = crm.contacts.update(
    contact.id,
    ContactUpdate(
        emails=(
            ContactEmail(
                "ada.new@example.com",
                is_primary=True,
            ),
        ),
    ),
)
~~~

This is an explicit replacement of the Contact's email collection.

It is not an implicit "append one email" command.

That distinction helps keep domain state deterministic across adapters.

## 14. Contact lifecycle

ContactStatus defines:

~~~text
ACTIVE
INACTIVE
ARCHIVED
~~~

A Contact is active by default.

You may create one as inactive:

~~~python
from pycrmkit.contacts import ContactStatus

contact = crm.contacts.create(
    display_name="Dormant Customer",
    status=ContactStatus.INACTIVE,
)
~~~

You can also move between active/inactive through ContactUpdate:

~~~python
contact = crm.contacts.update(
    contact.id,
    ContactUpdate(
        status=ContactStatus.INACTIVE,
    ),
)
~~~

But archival is deliberately different.

## 15. Archive through the dedicated operation

Do this:

~~~python
archived = crm.contacts.archive(contact.id)
~~~

Do **not** do this:

~~~python
crm.contacts.update(
    contact.id,
    ContactUpdate(
        status=ContactStatus.ARCHIVED,
    ),
)
~~~

The second form is rejected with InvalidStateError because archival needs its
own lifecycle operation and timestamp semantics.

The archive operation sets:

~~~text
status      = archived
archived_at = current domain clock
updated_at  = same archive timestamp
~~~

Archival is idempotent at the aggregate/repository contract level.

## 16. Archived Contacts are immutable

Once archived, normal profile updates are rejected:

~~~python
crm.contacts.update(
    archived.id,
    ContactUpdate(
        last_name="Changed",
    ),
)
~~~

raises:

~~~text
InvalidStateError
code = contact.archived
~~~

This protects historical CRM state from accidental post-archive mutation.

## 17. Search Contacts

Use ContactQuery:

~~~python
from pycrmkit.contacts import ContactQuery

page = crm.contacts.search(
    ContactQuery(
        name="Ada",
    ),
)
~~~

Available semantic filters are:

~~~text
status
email
phone
name
owner_id
source
include_archived
~~~

These filters belong to the backend-independent repository contract.

So application code can express the same Contact search whether the adapter is:

~~~text
Memory
SQLAlchemy/PostgreSQL
another contract-conformant adapter
~~~

## 18. Search by normalized email

You may search with a differently cased email:

~~~python
page = crm.contacts.search(
    ContactQuery(
        email="ADA@EXAMPLE.COM",
    ),
)
~~~

ContactQuery normalizes the email before it reaches the repository contract.

The search therefore uses normalized CRM equality rather than the presentation
case.

## 19. Search by normalized phone

Likewise:

~~~python
page = crm.contacts.search(
    ContactQuery(
        phone="+44 20 7946 0958",
    ),
)
~~~

normalizes the phone before repository matching.

## 20. Name search

Name search is a semantic contains-style filter over the Contact identity text.

Example:

~~~python
page = crm.contacts.search(
    ContactQuery(
        name="love",
    ),
)
~~~

can match a Contact whose identity text includes `Lovelace`.

The stable contract requires adapter parity for the query semantics; application
code should not depend on backend-specific SQL/ORM query APIs.

## 21. Source search

The source field is useful for acquisition/integration provenance:

~~~python
crm.contacts.create(
    display_name="Imported Customer",
    source="website",
)
~~~

Then:

~~~python
page = crm.contacts.search(
    ContactQuery(
        source="WEBSITE",
    ),
)
~~~

The Memory adapter performs case-insensitive source equality, and persistent
adapters are contract-qualified against the shared repository semantics.

## 22. Pagination

Contact search returns a Page[Contact].

Use OffsetPageRequest:

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = crm.contacts.search(
    ContactQuery(),
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

The stable bounds are:

~~~text
default limit = 50
maximum limit = 200
offset        = non-negative integer
~~~

Every repository adapter must return an exact total and deterministic offset
pagination.

## 23. Archived Contacts and search

Archived Contacts are excluded by default:

~~~python
crm.contacts.archive(contact.id)

page = crm.contacts.search()

assert contact.id not in {
    item.id
    for item in page.items
}
~~~

To include them:

~~~python
page = crm.contacts.search(
    ContactQuery(
        include_archived=True,
    ),
)
~~~

You can also combine archival inclusion with an explicit status filter:

~~~python
page = crm.contacts.search(
    ContactQuery(
        status=ContactStatus.ARCHIVED,
        include_archived=True,
    ),
)
~~~

## 24. Error model

Contact operations use PyCRMKit's public typed exception hierarchy.

Common errors include:

| Error | Typical Contact case |
| --- | --- |
| ValidationError | missing identity, invalid email/phone/address, multiple primaries |
| ConflictError | duplicate normalized email/phone within one Contact |
| NotFoundError | get/update/archive unknown ContactId |
| InvalidStateError | direct archived creation, archive through update, mutation after archive |

All PyCRMKit errors provide:

~~~text
message
code
context
~~~

and a structured `as_dict()` representation suitable for API adapters.

Example:

~~~python
from pycrmkit.exceptions import ValidationError

try:
    crm.contacts.create()
except ValidationError as exc:
    print(exc.code)
    print(exc.as_dict())
~~~

## 25. Contact events and audit

When using the CRM facade, mutations are not just repository writes.

The facade records change semantics such as:

~~~text
contact.created
contact.updated
contact.archived
~~~

and includes actor/correlation context when configured.

For example:

~~~python
crm = CRM.memory().with_context(
    actor_id="agent-42",
    correlation_id="contact-onboarding-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)
~~~

This becomes important later when we explore Events, Audit and production
request tracing.

## 26. Repository extension contract

Most applications should use:

~~~text
crm.contacts
~~~

But adapter authors need the ContactRepository protocol:

~~~text
get(ContactId) -> Contact
find(ContactId) -> Contact | None
save(Contact) -> None
archive(ContactId, datetime) -> Contact
search(ContactQuery, OffsetPageRequest) -> Page[Contact]
~~~

A critical detail is that `save()` does **not** commit an outer transaction.
Commit ownership belongs to the Unit of Work.

This separation is what allows one transaction to coordinate Contact changes
with other repositories, events and audit records.

## 27. Complete Contact example

~~~python
from pycrmkit import CRM
from pycrmkit.contacts import (
    Address,
    ContactEmail,
    ContactPhone,
    ContactQuery,
    ContactUpdate,
)
from pycrmkit.core.pagination import OffsetPageRequest

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="contacts-guide-001",
)

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
    emails=(
        ContactEmail(
            "Ada@Example.com",
            is_primary=True,
        ),
    ),
    phones=(
        ContactPhone(
            "+44 20 7946 0958",
            is_primary=True,
        ),
    ),
    addresses=(
        Address(
            line1="12 St James's Square",
            city="London",
            postal_code="SW1Y 4LB",
            country_code="GB",
            is_primary=True,
        ),
    ),
    source="zero-to-hero",
    metadata={
        "segment": "strategic",
    },
)

assert contact.display_name == "Ada Lovelace"
assert contact.emails[0].normalized == "ada@example.com"
assert contact.phones[0].normalized == "+442079460958"

contact = crm.contacts.update(
    contact.id,
    ContactUpdate(
        last_name="Byron",
    ),
)

assert contact.display_name == "Ada Byron"

page = crm.contacts.search(
    ContactQuery(
        email="ADA@EXAMPLE.COM",
    ),
    OffsetPageRequest(
        limit=10,
    ),
)

assert page.total == 1
assert page.items[0].id == contact.id

archived = crm.contacts.archive(contact.id)

assert archived.status.value == "archived"
assert crm.contacts.search().total == 0

with_archived = crm.contacts.search(
    ContactQuery(
        include_archived=True,
    ),
)

assert with_archived.total == 1
~~~

## 28. What happens internally?

A create/update/archive operation through the facade follows:

~~~text
Application
    ↓
crm.contacts
    ↓
ContactsAPI
    ↓
Unit of Work
    ↓
ContactService
    ↓
Contact validation / normalization
    ↓
ContactRepository
    ↓
event + audit staging
    ↓
commit
~~~

The Contact domain therefore stays independent of whether the final adapter is
in-memory or PostgreSQL-backed.

## Common mistakes

### Using raw strings instead of ContactEmail / ContactPhone / Address

These Value Objects own normalization and validation. Bypassing them also
bypasses part of the domain model.

### Treating `None` and omitted updates as equivalent

They are deliberately different. `UNSET` means "leave unchanged"; `None`
means "clear this nullable field".

### Archiving with ContactUpdate

Archival has dedicated semantics. Use `crm.contacts.archive(...)`.

### Assuming archived Contacts appear in ordinary searches

They do not. Set `include_archived=True` when history or reconciliation needs
them.

### Assuming local email/phone uniqueness means global deduplication

The Contact aggregate prevents duplicate points **inside itself**. Detecting
duplicate people across separate Contact records belongs to the Deduplication
layer later in the course.

### Reaching into an ORM for Contact queries

Use ContactQuery at the application boundary. Backend-specific query APIs break
adapter portability and bypass the stable repository contract.

## Testing Contact workflows

A useful application-level test should verify observable behavior rather than
internal implementation classes:

~~~python
from pycrmkit import CRM
from pycrmkit.contacts import ContactQuery

def test_customer_can_be_created_and_found() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
        source="test",
    )

    page = crm.contacts.search(
        ContactQuery(
            source="test",
        ),
    )

    assert [item.id for item in page.items] == [contact.id]
~~~

Later, repository-contract and PostgreSQL integration tests can validate that a
different adapter preserves the same semantics.

## What you learned

You can now explain and use:

- Contact as a typed aggregate;
- ContactId;
- identity requirements;
- derived vs explicit display names;
- ContactEmail normalization;
- ContactPhone normalization;
- Address validation;
- primary contact-point rules;
- ContactUpdate and UNSET semantics;
- active/inactive/archive lifecycle;
- archive immutability;
- ContactQuery;
- deterministic pagination;
- archived-search semantics;
- typed Contact errors;
- the ContactRepository extension contract.

## Next

The next planned chapter is **04 — Organizations**.

Organizations add the company/account side of the CRM model. Chapter 05 will
then introduce Relationships to connect Contacts and Organizations explicitly
instead of hiding that connection inside either aggregate.
