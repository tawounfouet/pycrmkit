# Django

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 26 exposed the CRM facade through FastAPI while keeping HTTP concerns
outside the domain. Django follows the same rule, but its integration point is
different: Django brings its own application registry, ORM, migration framework,
transaction manager and admin.

The current V1 architecture is:

~~~text
Django application
      |
      v
PyCRMKit Django app
      |
      +--> Django ORM persistence models
      +--> Django repository adapters
      +--> DjangoTransactionBridge
      +--> Django migrations
      +--> Django admin
      |
      v
CRM facade / domain services
      |
      v
backend-neutral repository contracts
~~~

The central rule is:

> Django models are persistence representations. They are not PyCRMKit domain
> entities, and Django does not redefine CRM business behavior.

## What you will learn

You will learn to:

- install and register the optional Django adapter;
- distinguish Django ORM models from domain entities;
- understand the current V1 Django persistence scope;
- understand Contact, Organization, Relationship and External Identity mapping;
- understand child-row ownership and typed reference persistence;
- understand repository contract equivalence;
- use DjangoTransactionBridge;
- understand explicit commit, rollback and ambient transactions;
- understand post-commit Domain Event semantics;
- understand the Django migration history;
- understand why Django migrations and Alembic migrations are separate;
- understand Django admin as an operational persistence view;
- understand PostgreSQL and installed-wheel qualification;
- prepare for the dedicated Django REST Framework chapter.

## 1. Django support is optional

Install it with:

~~~bash
pip install "pycrmkit[django]"
~~~

The stable dependency range is:

~~~text
Django >= 5.2, < 5.3
~~~

The core PyCRMKit package does not require Django.

## 2. Core import remains Django-free

A minimal installation can still execute:

~~~python
import pycrmkit
~~~

without importing Django transitively.

This boundary is explicitly tested.

## 3. Register the PyCRMKit application

Add:

~~~python
INSTALLED_APPS = [
    # ...
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
~~~

The AppConfig uses:

~~~text
name  = pycrmkit.integrations.django
label = pycrmkit_crm
~~~

## 4. The app label is intentionally specific

The label pycrmkit_crm avoids a generic application name that could collide
with a consumer project.

## 5. App registration has no domain side effects

PyCRMKitDjangoConfig registers integration metadata only.

It does not create domain entities, open transactions or mutate schema during
application startup.

## 6. Migrations remain explicit

Adding the app to INSTALLED_APPS does not apply database migrations.

Schema changes remain deployment operations.

## 7. Django remains outside the domain

Dependency direction is:

~~~text
Django application
      |
      v
Django adapter
      |
      v
Repository protocols / CRM facade
      |
      v
Domain
~~~

The domain does not inherit from django.db.models.Model.

## 8. Domain entities and ORM models are distinct

The core invariant is:

~~~text
Contact          != ContactModel
Organization     != OrganizationModel
Relationship     != RelationshipModel
ExternalIdentity != ExternalIdentityModel
~~~

## 9. Django models are persistence representations

They define database columns, indexes, ownership foreign keys, ordering,
JSON storage, migrations and admin integration.

They do not own CRM business behavior.

## 10. Current V1 Django repository scope

PyCRMKit 1.0.x exposes Django repositories for:

~~~text
contacts
organizations
relationships
external_identities
~~~

This is intentionally a bounded persistence adapter.

## 11. Historical scope matters

The stable 0.8.x Django line originally covered:

~~~text
Contacts
Organizations
Relationships
~~~

The 0.9.0a1 milestone added:

~~~text
ExternalIdentityModel
DjangoExternalIdentityRepository
0002_external_identity
~~~

PyCRMKit 1.0 includes that extension.

## 12. The bridge is not the complete UnitOfWork

There are no current Django repository implementations in this bridge for every
PyCRMKit family such as Activities, Tasks, Timeline, Leads, Opportunities,
Pipelines, Tags, Custom Fields, Communication, Webhooks or Audit.

Do not advertise DjangoTransactionBridge as the framework-wide UnitOfWork.

## 13. Contact persistence is aggregate-oriented

~~~text
ContactModel
   |
   +--> ContactEmailModel
   +--> ContactPhoneModel
   +--> ContactAddressModel
~~~

The parent stores scalar Contact state. Child rows persist ordered value-object
collections.

## 14. Contact child rows are owned persistence

Each child model has a ForeignKey to ContactModel with cascading deletion.

This is persistence ownership, not a new domain relationship.

## 15. Contact collection order is persisted

Email, phone and address rows contain a position column.

Hydration sorts by:

~~~text
position
id
~~~

before reconstructing domain tuples.

## 16. Contact save replaces child collections

DjangoContactRepository.save performs:

~~~text
upsert ContactModel
      |
      v
delete old child rows
      |
      v
bulk-create current emails / phones / addresses
~~~

The stored representation follows the current aggregate value.

## 17. Contact hydration reconstructs domain types

The repository rebuilds:

~~~text
Contact
ContactId
EntityId
ContactStatus
ContactEmail
ContactPhone
Address
VerificationState
~~~

It never returns ContactModel.

## 18. Datetimes return through the PyCRMKit UTC boundary

The repository applies the framework UTC normalization helper before creating
domain objects.

## 19. Contact search preserves repository semantics

DjangoContactRepository supports:

~~~text
archive visibility
status
normalized email
normalized phone
name
owner
source
~~~

## 20. Contact search uses Django ORM expressions internally

Name search composes first name, last name and display name using ORM
expressions and case-normalized matching.

Query construction remains an adapter detail.

## 21. Contact ordering is deterministic

The final ordering is:

~~~text
created_at
id
~~~

matching the portable repository contract.

## 22. Pagination computes exact total

The shared Django pagination helper performs a QuerySet count before slicing by
offset and limit, then returns the backend-neutral Page type.

## 23. Organization persistence follows the same pattern

~~~text
OrganizationModel
   |
   +--> OrganizationDomainModel
   +--> OrganizationAddressModel
~~~

Domain and address rows are ownership children.

## 24. Organization save replaces child collections

The repository upserts the parent and replaces domain/address rows from the
current Organization aggregate.

## 25. Organization hydration returns domain objects

It reconstructs Organization, OrganizationId, EntityId, OrganizationStatus,
OrganizationDomain and OrganizationAddress.

Django models remain internal.

## 26. Organization search remains portable

Supported query semantics include:

~~~text
archive visibility
status
normalized domain
name
registration number
owner
source
~~~

## 27. Relationship uses one persistence row

RelationshipModel stores:

~~~text
id
source_kind
source_id
target_kind
target_id
relationship_type
valid_from
valid_until
role
title
is_primary
metadata
created_at
updated_at
~~~

## 28. Relationship endpoints are typed references, not ORM FKs

Source and target are stored as kind + id.

They are not Django ForeignKeys to ContactModel or OrganizationModel.

## 29. The adapter restores RelationshipEndpoint types

Hydration maps the stored kind to ContactId or OrganizationId and rebuilds a
domain RelationshipEndpoint.

## 30. Relationship direction is preserved

source and target stay distinct.

The adapter does not collapse them into an undirected database association.

## 31. Relationship query supports either endpoint

RelationshipQuery.entity matches either the source or target kind/id pair.

## 32. Temporal relationship semantics stay domain-compatible

The repository supports active_at and include_ended through valid_from and
valid_until filtering.

## 33. Ending a relationship remains a domain transition

The adapter:

~~~text
loads Relationship
      |
      v
calls relationship.end(ended_at)
      |
      v
saves resulting domain state
~~~

The ORM does not invent the transition.

## 34. External Identities extend the current V1 Django adapter

ExternalIdentityModel stores:

~~~text
id
system
external_id
entity_type
entity_id
metadata
created_at
updated_at
~~~

## 35. Provider identity uniqueness is enforced

The model declares:

~~~text
UNIQUE(system, external_id)
~~~

with constraint name:

~~~text
uq_dj_external_identity_system_id
~~~

## 36. Entity lookup is indexed

The model adds:

~~~text
ix_dj_external_identity_entity
~~~

over entity_type and entity_id.

## 37. External Identity ownership is a typed reference

entity_type and entity_id are not Django ForeignKeys to ContactModel or
OrganizationModel.

The repository restores typed domain IDs instead.

## 38. External identity keys are normalized

find and remove normalize system and external_id before querying.

This matches the provider-neutral External Identity contract.

## 39. Different-owner conflicts remain domain errors

A provider key attached to a different entity raises:

~~~text
ConflictError
code = external_identity.owner.conflict
~~~

## 40. Same-owner duplicate remains typed

A duplicate mapping with a different persistence identity but the same entity
raises:

~~~text
DuplicateError
code = external_identity.duplicate
~~~

## 41. Typed owner IDs survive hydration

Known entity types restore:

~~~text
contact      -> ContactId
organization -> OrganizationId
other        -> EntityId
~~~

## 42. Django repositories replay shared contracts

The Django implementations are tested against the same reusable repository
contracts used to qualify other adapters.

The compatibility target is observable behavior, not identical implementation.

## 43. QuerySets never leak through repository contracts

Callers receive domain objects, Page values, None and typed PyCRMKit errors.

They do not receive QuerySet instances.

## 44. Model instances never leak through repository contracts

Application/domain code does not need Model.save, objects.filter, select_related
or other ORM APIs.

## 45. Django has its own migration history

The current V1 chain is:

~~~text
0001_initial
      |
      v
0002_external_identity
~~~

## 46. 0001_initial creates the original Django persistence scope

It creates Contacts and child rows, Organizations and child rows, and
Relationships.

## 47. 0002_external_identity extends the schema

It creates ExternalIdentityModel plus its unique constraint and entity lookup
index.

## 48. Apply migrations through normal Django tooling

~~~bash
python manage.py migrate pycrmkit_crm
~~~

or:

~~~bash
python manage.py migrate
~~~

## 49. Migration discovery is tested

The qualification suite verifies both revisions exist in Django's migration
graph.

## 50. Applied revision state is tested

MigrationRecorder is expected to contain:

~~~text
pycrmkit_crm / 0001_initial
pycrmkit_crm / 0002_external_identity
~~~

## 51. Model/migration drift is a gate

CI runs:

~~~bash
python manage.py makemigrations pycrmkit_crm --check --dry-run
~~~

A model change without a matching Django migration fails qualification.

## 52. Empty-to-latest is qualified

The test suite verifies:

~~~text
migrate pycrmkit_crm zero
        |
        v
adapter tables absent
        |
        v
migrate pycrmkit_crm
        |
        v
all expected tables present
~~~

## 53. Django migrations and Alembic are separate histories

SQLAlchemy/PostgreSQL persistence uses Alembic.

The Django ORM adapter uses Django migrations.

These are distinct infrastructure strategies.

## 54. Behavioral parity does not imply migration interchangeability

Both adapters may use pycrmkit-prefixed physical table names, but their
migration histories are not automatically interchangeable.

## 55. Do not run both histories blindly against one schema

Choose the persistence adapter and migration owner explicitly unless a dedicated
interoperability migration has been designed.

## 56. DjangoTransactionBridge gives explicit transaction intent

Typical use:

~~~python
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

with DjangoTransactionBridge() as bridge:
    bridge.contacts.save(contact)
    bridge.organizations.save(organization)
    bridge.commit()
~~~

## 57. Entering the bridge opens transaction.atomic

The bridge marks itself active, binds its repository adapters and enters a
Django atomic block.

## 58. Repository access requires an active bridge

Before entering the context, repository access or commit raises:

~~~text
InvalidStateError
code = django.transaction.not_active
~~~

## 59. Explicit commit is required

Leaving the context without commit rolls the current atomic block back.

This mirrors PyCRMKit's explicit transaction intent.

## 60. Uncommitted multi-repository work rolls back together

Saving Contact and Organization then leaving without commit persists neither.

## 61. Exceptions roll back

An exception escaping the bridge before commit causes database rollback.

## 62. Commit closes the current bridge transaction

A successful top-level flow is:

~~~text
repository writes
      |
      v
Django atomic COMMIT
      |
      v
durable database state
      |
      v
publish pending Domain Events
~~~

## 63. Commit failures are normalized

Django DatabaseError during commit becomes:

~~~text
RepositoryError
code = django.transaction.commit_failed
~~~

## 64. Begin and rollback failures are normalized too

The bridge uses:

~~~text
django.transaction.begin_failed
django.transaction.rollback_failed
~~~

for those infrastructure failures.

## 65. Explicit rollback keeps the bridge usable

bridge.rollback:

~~~text
rolls back current work
clears pending events
opens a fresh atomic block
keeps the bridge active
~~~

## 66. Work can continue after rollback

The qualified scenario is:

~~~text
save Contact
rollback
verify Contact absent
save Organization
commit
verify Organization persisted
~~~

## 67. Repository access after commit is rejected

After successful commit, the bridge transaction is closed.

Further repository access raises:

~~~text
django.transaction.already_committed
~~~

## 68. The bridge stages Domain Events

bridge.add_event stores pending events until the relevant transaction has
actually committed.

## 69. Top-level events publish after commit

If the bridge owns the top-level transaction, event publication occurs only
after atomic commit succeeds.

## 70. Subscriber failure cannot undo committed state

A post-commit subscriber may raise, but the already committed database state
remains durable.

## 71. Ambient transactions use Django savepoints

The bridge can run inside an existing transaction.atomic block.

Its internal atomic block participates using Django savepoint semantics.

## 72. Inner commit may only release a savepoint

~~~text
outer transaction.atomic
      |
      v
DjangoTransactionBridge
      |
      v
bridge.commit
      |
      v
savepoint released
      |
      v
outer transaction still open
~~~

## 73. Events wait for the real outer commit

When an ambient transaction exists, the bridge registers publication through
transaction.on_commit.

No event is published merely because the inner savepoint was released.

## 74. Outer rollback discards writes and event callback

If the outer transaction rolls back after bridge.commit, both the database
changes and pending on_commit callback are discarded.

## 75. The bridge is intentionally bounded

The current bridge exposes:

~~~text
contacts
organizations
relationships
external_identities
~~~

It is not the complete framework UnitOfWork.

## 76. The reference app confines any UnitOfWork cast to composition

The example application casts DjangoTransactionBridge only inside its own
wiring function and documents the limited adapter scope there.

## 77. Audit persistence is disabled in the reference Django CRM

The reference configuration uses events but sets audit_enabled to false because
the current Django bridge has no Audit repository.

## 78. Django admin is an operational persistence view

The admin module registers:

~~~text
ContactModel
OrganizationModel
RelationshipModel
~~~

## 79. ExternalIdentityModel is not currently registered in admin

The current admin helper set covers the original three parent persistence
models only.

## 80. Contact admin exposes child rows inline

Contact admin includes email, phone and address inlines.

## 81. Organization admin exposes child rows inline

Organization admin includes domain and address inlines.

## 82. Admin is not the business API

Admin views operate over persistence representations.

Domain correctness still belongs to PyCRMKit services, entities, policies and
facades.

## 83. Business logic is not moved into Django signals

The stable adapter does not redefine core CRM lifecycle rules through signals.

## 84. DRF remains a separate optional integration

Installing:

~~~bash
pip install "pycrmkit[django]"
~~~

does not install Django REST Framework.

DRF uses its own extra and is the subject of Chapter 28.

## 85. The reference application uses PostgreSQL 17

The production-reference path is:

~~~text
Django 5.2
   |
   v
DjangoTransactionBridge
   |
   v
Django repositories
   |
   v
Django ORM
   |
   v
PostgreSQL 17
~~~

## 86. Reference settings require PYCRMKIT_DATABASE_URL

The example parses a PostgreSQL URL from:

~~~text
PYCRMKIT_DATABASE_URL
~~~

and rejects unrelated database schemes.

## 87. Lightweight contract tests use SQLite

The Django integration unit/contract environment uses in-memory SQLite for fast
repository, migration and transaction checks.

## 88. Production-reference E2E uses PostgreSQL

A dedicated workflow starts PostgreSQL 17 and repeats the Django integration
through the reference application.

## 89. Deployment remains migration-first

~~~text
configure PYCRMKIT_DATABASE_URL
      |
      v
python manage.py migrate
      |
      v
python manage.py check
      |
      v
start Django
~~~

Application startup does not silently mutate the schema.

## 90. E2E uses two Python processes

The smoke test separates:

~~~text
seed process
      |
      v
persist only IDs
      |
      v
fresh verify process
~~~

This prevents process-local state from masquerading as persistence.

## 91. Seed creates the connected CRM graph

The reference HTTP path creates Contact, Organization and Relationship.

It also attaches an External Identity through the CRM facade.

## 92. Verify reloads everything from PostgreSQL

A fresh Django process resolves the External Identity and reloads Contact,
Organization and Relationship state.

## 93. Verify mutates persisted state

The second process updates the Contact and ends the Relationship.

This proves read/write behavior after restart.

## 94. Verify checks admin and migration state

The smoke test verifies admin registration and recorded Django migrations in the
fresh process.

## 95. The same path runs from a built wheel

CI resets PostgreSQL, installs the built wheel with Django/DRF/PostgreSQL extras,
applies packaged migrations and reruns the two-process E2E.

## 96. Core-only wheel remains Django-free

A clean environment installs only the base wheel and verifies Django and DRF
are absent while import pycrmkit succeeds.

## 97. Django-only wheel remains DRF-free

The Django integration gate installs wheel[django] and verifies rest_framework
is not present.

## 98. Packaged migration execution is qualified

The clean wheel environment executes the Django migration modules delivered to
consumers.

## 99. Installed-wheel transaction behavior is qualified

The wheel smoke migrates an in-memory Django database, writes a Contact through
DjangoTransactionBridge and reloads it through DjangoContactRepository.

## 100. A useful mental model

~~~text
Domain Entity
      |
      v
Repository Contract
      |
      v
Django Repository
      |
      v
Django ORM Model
      |
      v
Django Migration History
      |
      v
Database
~~~

Django is an implementation adapter below the domain contract.

## Common mistakes

### Making Django models the domain entities

They are persistence representations only.

### Returning QuerySets from repository contracts

Repositories return domain objects and Page values.

### Calling Model.objects from domain services

Keep ORM access inside the adapter.

### Treating DjangoTransactionBridge as complete UnitOfWork

Its V1 repository scope is bounded.

### Forgetting explicit commit

Exit without commit rolls back.

### Assuming inner savepoint commit is final

An outer atomic transaction can still roll everything back.

### Publishing events before the outer transaction commits

Ambient transactions defer events through on_commit.

### Running migrations during import or startup

Schema evolution is an explicit deployment concern.

### Mixing Alembic and Django histories blindly

They are separate persistence adapter lifecycles.

### Treating admin as the canonical business interface

Admin is operational persistence tooling.

### Assuming every model has admin registration

ExternalIdentityModel is not currently registered there.

### Assuming the Django extra includes DRF

DRF is separate.

### Qualifying only on SQLite

The production-reference path runs PostgreSQL 17 and a two-process E2E.

## Testing the Django adapter

Registration tests should cover:

~~~text
AppConfig loading
pycrmkit_crm label
core import without Django
optional dependency boundary
~~~

Repository tests should cover:

~~~text
Contact contract
Organization contract
Relationship contract
External Identity contract
typed IDs after hydration
deterministic pagination
lifecycle semantics
~~~

Migration tests should cover:

~~~text
0001_initial
0002_external_identity
zero -> latest
latest -> zero
makemigrations --check --dry-run
MigrationRecorder state
~~~

Transaction tests should cover:

~~~text
not-active errors
multi-repository commit
uncommitted exit rollback
exception rollback
rollback-and-continue
top-level post-commit events
ambient savepoints
outer rollback
subscriber failure after commit
access-after-commit rejection
~~~

Admin tests should cover:

~~~text
Contact registration
Organization registration
Relationship registration
Contact inlines
Organization inlines
~~~

Production E2E should cover:

~~~text
PostgreSQL 17
Django migrations
system check
Contact / Organization / Relationship
External Identity round trip
fresh Python process
reload and mutation
admin smoke
migration state
~~~

Packaging tests should cover:

~~~text
core-only wheel without Django
django wheel without DRF
packaged migrations
installed-wheel transaction smoke
installed-wheel PostgreSQL E2E
~~~

## What you learned

You can now explain:

- why Django remains optional;
- PyCRMKitDjangoConfig and the pycrmkit_crm label;
- Django ORM models versus domain entities;
- the current V1 Django repository scope;
- Contact/Organization child ownership;
- Relationship typed-reference persistence;
- External Identity persistence and migration 0002;
- shared repository-contract qualification;
- QuerySet encapsulation;
- DjangoTransactionBridge explicit commit/rollback;
- ambient transaction and savepoint semantics;
- post-commit Domain Event publication;
- Django migration history versus Alembic;
- admin as an operational persistence view;
- PostgreSQL two-process E2E;
- installed-wheel dependency and migration qualification.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter              ✅
23 SQLAlchemy                  ✅
24 PostgreSQL                  ✅
25 Migrations                  ✅
26 FastAPI                     ✅
27 Django                      ✅
28 Django REST Framework       ← NEXT
29 Transactions & Unit of Work
30 Context, Events & Audit
31 Error Handling
32 Security & Privacy
~~~

The framework now has two application integration directions:

~~~text
FastAPI -> CRM facade

Django -> Django adapter / CRM facade
~~~

Both preserve a framework-agnostic domain.

## Next

The next chapter is **28 - Django REST Framework**.

The architecture becomes:

~~~text
HTTP Request
      |
      v
DRF Serializer / ViewSet
      |
      v
request-scoped CRM facade
      |
      v
DjangoTransactionBridge
      |
      v
Django repositories
      |
      v
PostgreSQL
~~~

The next learning question is:

> How does PyCRMKit expose its bounded Django persistence surface through DRF
> serializers, ViewSets, pagination, request context and stable error mapping
> without letting DRF serializers or Django ORM models become the domain API?
