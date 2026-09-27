# External Identities

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter begins **LEVEL 5 - Data Operations**.

LEVEL 4 completed the Communication & Automation layer. The next challenge is
data integration: the same customer may already exist in HubSpot, Salesforce,
a legacy CRM, an ERP, a billing platform or a support tool.

PyCRMKit must answer:

> How can one external-system record be mapped to a stable CRM entity without
> polluting Contact or Organization models with provider-specific IDs?

The answer is **ExternalIdentity**.

## What you will build

You will:

- understand the provider-neutral ExternalIdentity model;
- normalize external system codes;
- preserve provider-owned external-ID case;
- attach external records to Contacts and Organizations;
- attach other CRM entity kinds through EntityReference;
- understand global uniqueness of the pair system + external_id;
- replay attach idempotently for the same owner;
- detect ownership conflicts;
- resolve a CRM owner from an external record key;
- list external identities for an entity;
- detach mappings idempotently;
- understand metadata behavior;
- understand event emission and privacy;
- inspect repository semantics and deterministic ordering;
- understand typed owner restoration in persistence adapters;
- prepare for the Import, Deduplication and Merge chapters.

The mental model is:

~~~text
External system record
      |
      |  ("hubspot", "123456")
      v
ExternalIdentity
      |
      v
EntityReference
      |
      +--> Contact
      +--> Organization
      +--> Lead
      +--> another UUID-backed CRM entity kind
~~~

## 1. Why ExternalIdentity exists

A tempting design is to add fields such as:

~~~text
contact.hubspot_id
contact.salesforce_id
organization.erp_customer_id
organization.legacy_crm_id
~~~

That does not scale. Every integration would require changing core CRM
aggregates.

PyCRMKit instead models external identity as a separate bounded context:

~~~text
Contact does not know HubSpot
Organization does not know Salesforce
ExternalIdentity maps an external record to a CRM entity
~~~

## 2. Stable ExternalIdentity model

The V1 entity contains:

~~~text
ExternalIdentity
├── id
├── created_at
├── updated_at
├── system
├── external_id
├── entity_type
├── entity_id
└── metadata
~~~

Its typed identity is ExternalIdentityId.

## 3. The external-record key

One upstream record is defined by:

~~~text
(system, external_id)
~~~

Example:

~~~text
("hubspot", "123456")
~~~

This pair is globally unique across the external identity repository.

## 4. Ownership invariant

A single external record can belong to exactly one PyCRMKit entity.

~~~text
("hubspot", "123456")
        |
        +--> Contact A     valid

("hubspot", "123456")
        |
        +--> Contact A
        +--> Contact B     invalid
~~~

The owner is not part of the uniqueness key.

## 5. Why owner is not part of the key

The model deliberately chooses:

~~~text
UNIQUE(system, external_id)
~~~

rather than:

~~~text
UNIQUE(system, external_id, entity_type, entity_id)
~~~

This prevents one upstream record from silently pointing to two CRM entities.

## 6. normalize_external_system()

External system names become stable comparison keys.

~~~python
from pycrmkit.external_identities import normalize_external_system

assert normalize_external_system(" HubSpot CRM ") == "hubspot_crm"
~~~

Normalization performs:

~~~text
Unicode NFKC
trim
casefold
spaces/hyphens -> underscore
stable identifier validation
~~~

## 7. System identifier grammar

The normalized system code must match:

~~~text
^[a-z][a-z0-9_.]{0,127}$
~~~

Meaning:

- first character is a lowercase ASCII letter;
- remaining characters may include lowercase letters, digits, underscore or dot;
- maximum total length is 128 characters.

## 8. System normalization examples

~~~text
"HubSpot"     -> "hubspot"
"HubSpot CRM" -> "hubspot_crm"
"legacy-crm"  -> "legacy_crm"
"ERP.EU"      -> "erp.eu"
~~~

## 9. Invalid system code

Examples such as an empty value, a code beginning with a digit, or a code
containing a slash are rejected.

Stable error:

~~~text
ValidationError
code = external_identity.system.invalid
~~~

## 10. normalize_external_id()

The external record identifier is normalized differently.

~~~python
from pycrmkit.external_identities import normalize_external_id

assert normalize_external_id("  AbC-123  ") == "AbC-123"
~~~

It performs Unicode NFKC normalization and outer trimming, but deliberately
does not case-fold the value.

## 11. External ID case is provider-owned

These remain distinct keys:

~~~text
"ABC-123"
"abc-123"
~~~

PyCRMKit does not assume an upstream provider treats IDs case-insensitively.

## 12. Empty external ID

After normalization and trim, an empty value raises:

~~~text
ValidationError
code = external_identity.external_id.empty
~~~

## 13. Maximum external ID length

Maximum length is 512 characters.

Longer identifiers raise:

~~~text
external_identity.external_id.too_long
~~~

## 14. Internal whitespace is preserved

External ID normalization does not collapse internal whitespace.

The provider owns the identifier semantics. PyCRMKit only removes surrounding
presentation noise and applies Unicode normalization.

## 15. Entity ownership fields

ExternalIdentity stores:

~~~text
entity_type
entity_id
~~~

entity_type uses the generic EntityReference kind normalization.

entity_id must be a UUID-backed PyCRMKit identifier.

## 16. entity_id validation

A raw string or arbitrary Python object is invalid.

Stable error:

~~~text
external_identity.entity_id.invalid
~~~

## 17. EntityReference property

Every ExternalIdentity exposes:

~~~python
reference = identity.entity
~~~

which is equivalent to:

~~~python
EntityReference(
    identity.entity_type,
    identity.entity_id,
)
~~~

This gives framework-neutral ownership without loading the aggregate.

## 18. same_entity()

The helper same_entity compares ownership using:

~~~text
entity kind
+
string UUID value
~~~

It does not require the exact UUIDId subclass to match.

That matters after persistence round trips where known kinds may be restored to
more specific ID classes.

## 19. Stable facade

The V1 application surface is:

~~~text
crm.external_identities.attach
crm.external_identities.resolve
crm.external_identities.list_for_entity
crm.external_identities.detach
~~~

## 20. Attach a Contact

~~~python
contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

identity = crm.external_identities.attach(
    contact,
    system="hubspot",
    external_id="123456",
)
~~~

The Contact aggregate itself remains provider-neutral.

## 21. Attach an Organization

~~~python
organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

identity = crm.external_identities.attach(
    organization,
    system="salesforce",
    external_id="001XYZ",
)
~~~

## 22. Accepted facade targets

The high-level facade accepts directly:

~~~text
Contact
Organization
EntityReference
~~~

Contact and Organization are convenience forms converted internally to
EntityReference.

## 23. Explicit EntityReference target

For another CRM kind:

~~~python
from pycrmkit.core.references import EntityReference

identity = crm.external_identities.attach(
    EntityReference(
        "lead",
        lead.id,
    ),
    system="legacy_crm",
    external_id="lead-42",
)
~~~

## 24. Unsupported target Python type

Passing an object that is not EntityReference, Contact or Organization raises
TypeError.

## 25. EntityReference does not load the target aggregate

This is an important V1 boundary.

For a manually constructed EntityReference, the facade validates the reference
shape but does not query a repository to prove the target aggregate exists.

Applications needing referential-existence validation for arbitrary entity
kinds must apply that policy before attach.

## 26. Metadata

Attach accepts optional mapping metadata:

~~~python
identity = crm.external_identities.attach(
    contact,
    system="hubspot",
    external_id="123456",
    metadata={
        "portal": "eu",
        "source": "migration",
    },
)
~~~

Metadata is copied into a plain dict on the ExternalIdentity.

## 27. First attach flow

~~~text
normalize system
normalize external ID
        |
        v
find existing pair
        |
        +--> missing
               |
               v
        create ExternalIdentity
               |
               v
        repository.save
~~~

IDFactory and Clock are injected into the service.

## 28. Same-owner replay is idempotent

~~~python
first = crm.external_identities.attach(
    contact,
    system="hubspot",
    external_id="123456",
    metadata={"source": "initial"},
)

replay = crm.external_identities.attach(
    contact,
    system="HUBSPOT",
    external_id="123456",
    metadata={"source": "retry"},
)

assert replay == first
~~~

No new mapping is created.

## 29. Replay does not update metadata

The replay returns the existing mapping immediately.

~~~python
assert replay.metadata == {
    "source": "initial",
}
~~~

The second metadata payload is ignored.

## 30. Attach is not a metadata upsert

Stable V1 exposes no metadata-update method for ExternalIdentity through the
facade.

Attach means:

> ensure this external key belongs to this owner.

It does not mean:

> replace or merge mapping metadata.

## 31. First attach event

A first-time attach emits:

~~~text
external_identity.attached
~~~

The event aggregate is the mapped CRM owner.

## 32. Replay event behavior

A same-owner attach replay emits no second external_identity.attached event.

The facade checks whether the mapping existed before recording the change.

## 33. Ownership conflict

If the external key already belongs to another entity:

~~~text
ConflictError
code = external_identity.owner.conflict
~~~

Example:

~~~text
("hubspot", "42") -> Contact A

attempt:
("hubspot", "42") -> Contact B

=> conflict
~~~

## 34. Conflict context

The conflict context carries:

~~~text
system
owner_type
owner_id
~~~

The external_id is not required in that diagnostic context.

## 35. Repository defense in depth

The service checks ownership before save.

Official repositories enforce the same invariant again.

This protects the persistence extension point even if custom application code
bypasses ExternalIdentityService.

## 36. Repository duplicate vs owner conflict

At repository level:

~~~text
same key + different owner
-> ConflictError
   external_identity.owner.conflict

same key + same owner + different ExternalIdentity object
-> DuplicateError
   external_identity.duplicate
~~~

The service-level attach normally converts same-owner replay into an idempotent
return before reaching the duplicate branch.

## 37. Resolve

~~~python
identity = crm.external_identities.resolve(
    "hubspot",
    "123456",
)
~~~

resolve returns the ExternalIdentity mapping, not the Contact or Organization
aggregate.

## 38. Resolve then route by owner

~~~text
resolve external key
        |
        v
ExternalIdentity.entity
        |
        v
EntityReference(kind, id)
        |
        +--> crm.contacts.get(...)
        +--> crm.organizations.get(...)
        +--> another domain API
~~~

Cross-domain routing remains explicit.

## 39. Resolve normalization

resolve normalizes both inputs before repository lookup.

The system is case-folded and normalized.

The external ID is trimmed but case-preserving.

## 40. Missing resolve

Absence raises:

~~~text
NotFoundError
code = external_identity.not_found
~~~

## 41. Not-found privacy

The NotFoundError context contains normalized system information but does not
copy the external_id.

That avoids unnecessarily propagating a potentially sensitive upstream record
identifier.

## 42. find() vs resolve()

ExternalIdentityService exposes:

~~~text
find -> ExternalIdentity | None
resolve -> ExternalIdentity or NotFoundError
~~~

The high-level CRM facade exposes resolve.

## 43. List for an entity

~~~python
page = crm.external_identities.list_for_entity(
    contact,
)
~~~

The same Contact, Organization or EntityReference target forms are accepted.

## 44. Pagination

~~~python
page = crm.external_identities.list_for_entity(
    contact,
    OffsetPageRequest(
        limit=20,
        offset=0,
    ),
)
~~~

The normal Page contract applies.

## 45. Deterministic ordering

Official repositories order mappings for one owner by:

~~~text
system ASC
external_id ASC
id ASC
~~~

This ordering is part of the qualified repository behavior.

## 46. Detach

~~~python
removed = crm.external_identities.detach(
    "hubspot",
    "123456",
)

assert removed is True
~~~

## 47. Detach is idempotent

A later detach returns False:

~~~python
assert (
    crm.external_identities.detach(
        "hubspot",
        "123456",
    )
    is False
)
~~~

Absence is not exceptional.

## 48. Detach event

A successful detach emits:

~~~text
external_identity.detached
~~~

A no-op detach emits no event.

## 49. Detach event aggregate

The event aggregate identifies the former mapped owner.

For an Organization:

~~~text
aggregate_type = organization
aggregate_id = organization.id
~~~

## 50. Event payload privacy

Stable attach and detach payloads contain only:

~~~python
{
    "system": "legacy_crm",
}
~~~

They deliberately do not expose external_id.

## 51. Why external_id is omitted

External record identifiers can themselves be customer identifiers or sensitive
integration data.

They remain available through explicit authorized CRM APIs but are not copied
into generic event payloads.

## 52. Webhook consequence

Because Webhooks serialize DomainEvents, external_identity.attached and
external_identity.detached webhooks inherit the privacy-minimized payload.

Enabling webhook delivery does not automatically expose the external ID.

## 53. Audit behavior

The facade routes first attach and successful detach through
CRMRuntime.record_change.

The mutation records a change to the conceptual field:

~~~text
external_identities
~~~

rather than copying the external identifier itself into the event payload.

## 54. ExternalIdentityService

The provider-neutral service exposes:

~~~text
find
resolve
attach
list_for_entity
detach
~~~

Its dependencies are:

~~~text
ExternalIdentityRepository
IDFactory
Clock
~~~

Defaults are UUID4Factory and SystemClock.

## 55. Repository protocol

The public contract is:

~~~python
class ExternalIdentityRepository(Protocol):
    def find(
        self,
        system: str,
        external_id: str,
    ) -> ExternalIdentity | None:
        ...

    def save(
        self,
        identity: ExternalIdentity,
    ) -> None:
        ...

    def list_for_entity(
        self,
        entity: EntityReference,
        page: OffsetPageRequest,
    ) -> Page[ExternalIdentity]:
        ...

    def remove(
        self,
        system: str,
        external_id: str,
    ) -> bool:
        ...
~~~

## 56. Repository as extension point

Third-party persistence adapters should implement the domain-owned protocol
instead of exposing ORM representations as the application contract.

## 57. Memory repository key

MemoryExternalIdentityRepository stores mappings by:

~~~text
(system, external_id)
~~~

which mirrors the global uniqueness invariant directly.

## 58. Memory lookup boundary

The service always normalizes before calling the repository.

Memory find itself performs exact dictionary lookup and therefore expects
normalized values when used directly.

## 59. SQLAlchemy and Django lookup boundary

The official SQLAlchemy and Django repository adapters normalize system and
external_id inside find/remove as an additional defensive layer.

Application code should still prefer the service/facade contract.

## 60. Memory copy isolation

The Memory adapter deep-copies values when saving and returning them.

Mutating a retrieved identity does not silently mutate persisted state.

## 61. Database uniqueness

SQLAlchemy/PostgreSQL and Django schemas reinforce the same logical constraint:

~~~text
UNIQUE(system, external_id)
~~~

Database constraints supplement domain/service checks.

## 62. Typed owner restoration

Official SQLAlchemy and Django adapters restore known owner kinds to specific
typed IDs.

For entity_type contact:

~~~text
ContactId
~~~

For entity_type organization:

~~~text
OrganizationId
~~~

For other kinds:

~~~text
EntityId
~~~

## 63. Why typed restoration matters

After a database round trip, a Contact mapping still has a ContactId rather than
an untyped string.

The ExternalIdentity.entity property therefore preserves normal PyCRMKit typed
reference semantics.

## 64. Complete Contact example

~~~python
from pycrmkit import CRM

crm = CRM.memory()

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

identity = crm.external_identities.attach(
    contact,
    system=" HubSpot CRM ",
    external_id="  AbC-123  ",
    metadata={"portal": "eu"},
)

assert identity.system == "hubspot_crm"
assert identity.external_id == "AbC-123"
assert identity.entity.kind == "contact"
assert identity.entity.id == contact.id
~~~

## 65. Idempotent replay example

~~~python
retry = crm.external_identities.attach(
    contact,
    system="HUBSPOT CRM",
    external_id="AbC-123",
    metadata={"portal": "us"},
)

assert retry.id == identity.id
assert retry.metadata == {"portal": "eu"}
~~~

## 66. Resolve example

~~~python
resolved = crm.external_identities.resolve(
    "hubspot crm",
    "AbC-123",
)

assert resolved == identity
~~~

## 67. External-ID case example

If AbC-123 is stored, abc-123 remains a different external key.

The system name is case-insensitive through normalization; the provider-owned
external ID is not.

## 68. List example

~~~python
crm.external_identities.attach(
    contact,
    system="salesforce",
    external_id="003XYZ",
)

page = crm.external_identities.list_for_entity(
    contact,
)

assert [
    item.system
    for item in page.items
] == [
    "hubspot_crm",
    "salesforce",
]
~~~

## 69. Conflict example

~~~python
other = crm.contacts.create(
    display_name="Other Contact",
)

with pytest.raises(ConflictError) as error:
    crm.external_identities.attach(
        other,
        system="hubspot_crm",
        external_id="AbC-123",
    )

assert (
    error.value.code
    == "external_identity.owner.conflict"
)
~~~

## 70. Detach example

~~~python
assert crm.external_identities.detach(
    "hubspot_crm",
    "AbC-123",
) is True

assert crm.external_identities.detach(
    "hubspot_crm",
    "AbC-123",
) is False
~~~

## 71. Event privacy example

~~~python
events = []

crm.events.subscribe(
    "external_identity.attached",
    events.append,
)

crm.external_identities.attach(
    contact,
    system="legacy_crm",
    external_id="customer-secret-42",
)

event = events[0]

assert dict(event.payload) == {
    "system": "legacy_crm",
}

assert (
    "customer-secret-42"
    not in repr(event.payload)
)
~~~

## 72. EntityReference example

~~~python
lead_reference = EntityReference(
    "lead",
    lead.id,
)

mapping = crm.external_identities.attach(
    lead_reference,
    system="legacy_crm",
    external_id="LEAD-42",
)

assert mapping.entity == lead_reference
~~~

## 73. Reference-existence boundary

A manually constructed EntityReference may point to a UUID-backed entity kind
without the facade loading that entity first.

This is intentional flexibility, not a guarantee that the target exists.

## 74. Low-level service example

~~~python
from pycrmkit.external_identities import ExternalIdentityService
from pycrmkit.storage.memory import MemoryExternalIdentityRepository

service = ExternalIdentityService(
    MemoryExternalIdentityRepository(),
)

reference = EntityReference(
    "contact",
    contact.id,
)

identity = service.attach(
    reference,
    system="salesforce",
    external_id="003XYZ",
)
~~~

## 75. External identities and imports

ExternalIdentity is foundational for repeatable imports.

Conceptually:

~~~text
incoming row
    |
    v
(system, external_id)
    |
    v
resolve
    |
    +--> exists -> route to existing CRM entity
    |
    +--> missing -> create CRM entity -> attach mapping
~~~

Chapter 18 will build the import framework around this foundation.

## 76. External identity vs deduplication

ExternalIdentity is deterministic provider-record identity.

Deduplication asks whether two CRM records probably represent the same
real-world entity based on evidence.

These are different problems.

## 77. External identity vs merge

An ownership conflict should not silently merge CRM entities.

Contact Merge is a separate operation with explicit evidence, conflict policy
and provenance.

## 78. External identity vs authentication identity

ExternalIdentity maps CRM data records.

It does not represent:

~~~text
user login
OAuth subject
SSO identity
authentication principal
~~~

## 79. External identity vs synchronization state

ExternalIdentity does not track:

~~~text
last sync cursor
remote updated_at
ETag
sync status
retry count
~~~

Mapping identity and synchronization workflow are separate concerns.

## 80. Metadata privacy

Metadata is application-supplied integration data.

PyCRMKit does not automatically classify every metadata key.

Do not store secrets or unnecessary personal data there.

## 81. Repository contract qualification

A conforming adapter must preserve:

~~~text
save
find
missing returns None
list by owner
deterministic pagination
different-owner conflict
same-owner duplicate mapping protection
idempotent remove
~~~

## 82. Official adapters

The reusable repository contract is run against:

~~~text
MemoryExternalIdentityRepository
SQLAlchemyExternalIdentityRepository
DjangoExternalIdentityRepository
~~~

## 83. Persistence qualification

External identities are also covered by SQLAlchemy/PostgreSQL and
Django/PostgreSQL qualification paths.

They are not only an in-memory feature.

## Common mistakes

### Adding provider IDs directly to Contact

Use ExternalIdentity instead of extending core aggregates for each integration.

### Lowercasing external_id

Only system is case-folded. External-ID case belongs to the provider.

### Assuming owner participates in uniqueness

The global unique external key is system + external_id.

### Reattaching one key to another owner

That raises external_identity.owner.conflict.

### Using attach as metadata update

Same-owner replay returns the existing mapping unchanged.

### Expecting duplicate attach events

Idempotent replay emits no second attach event.

### Expecting detach absence to raise

Detach returns False when nothing existed.

### Putting external_id in event payloads

Stable attach/detach events intentionally expose only system.

### Expecting resolve to load Contact automatically

resolve returns ExternalIdentity; aggregate routing remains explicit.

### Passing a raw string as entity_id

EntityReference and ExternalIdentity require UUID-backed IDs.

### Assuming EntityReference attach verifies entity existence

The generic reference shape is validated, not repository existence.

### Bypassing the service and expecting repository save to be idempotent

Official repositories distinguish duplicate persistence identity from
application-level attach replay.

### Treating ExternalIdentity as fuzzy deduplication

It is deterministic external-record mapping.

### Treating ExternalIdentity as authentication identity

It maps CRM records, not users.

## Testing External Identity integrations

A strong test suite separates:

Normalization:

~~~text
system casefold
space/hyphen normalization
system grammar
external-ID NFKC + trim
external-ID case preservation
length limits
~~~

Ownership:

~~~text
first attach
same-owner replay
metadata replay behavior
different-owner conflict
Contact target
Organization target
EntityReference target
~~~

Lookup:

~~~text
resolve
not found
case-sensitive external ID
list ordering
pagination
~~~

Lifecycle and privacy:

~~~text
detach True
detach False on replay
attach event once
detach event once
event payload excludes external_id
~~~

Persistence:

~~~text
repository contract
copy isolation
global unique key
ContactId restore
OrganizationId restore
generic EntityId restore
~~~

## What you learned

You can now explain and use:

- ExternalIdentity;
- ExternalIdentityId;
- normalize_external_system;
- normalize_external_id;
- case-preserving external IDs;
- EntityReference ownership;
- same_entity;
- Contact and Organization convenience targets;
- generic EntityReference targets;
- reference-existence boundaries;
- metadata storage and replay semantics;
- same-owner idempotent attach;
- owner conflict detection;
- repository duplicate behavior;
- resolve;
- not-found privacy;
- list_for_entity;
- deterministic ordering;
- pagination;
- idempotent detach;
- external_identity.attached;
- external_identity.detached;
- privacy-minimized event payloads;
- ExternalIdentityService;
- ExternalIdentityRepository;
- Memory copy isolation;
- SQLAlchemy and Django adapter behavior;
- global database uniqueness;
- typed owner restoration;
- the distinction between external identity, synchronization, deduplication and
  authentication identity.

## LEVEL 5 in progress

Data Operations now begins with deterministic external record identity:

~~~text
External record
      |
      v
ExternalIdentity
      |
      v
CRM entity
~~~

## Next

The next chapter is **18 - Importing Data**.

We will move from one external mapping to a complete import pipeline:

~~~text
CSV / JSON / JSONL
        |
        v
row reader
        |
        v
mapping
        |
        v
normalization
        |
        v
validation
        |
        v
CRM operation
        |
        v
ExternalIdentity
        |
        v
Import report
~~~

The next learning question is:

> How does PyCRMKit import external data in a bounded-memory, deterministic and
> inspectable way while preserving domain validation and external identity?
