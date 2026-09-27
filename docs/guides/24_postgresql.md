# PostgreSQL

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 23 established the SQLAlchemy persistence boundary. This chapter moves
one layer lower and focuses on PostgreSQL, the production-reference relational
backend qualified by PyCRMKit.

The production persistence stack is:

~~~text
Domain / Application
        |
        v
Repository + UnitOfWork contracts
        |
        v
SQLAlchemy repositories
        |
        v
SQLAlchemyUnitOfWork
        |
        v
SQLAlchemy Session
        |
        v
psycopg
        |
        v
PostgreSQL
        |
        +--> constraints
        +--> indexes
        +--> foreign keys
        +--> exact numeric persistence
        +--> transactional commit/rollback
        +--> concurrent uniqueness enforcement
        +--> SQLSTATE diagnostics
~~~

The central persistence principle is:

> Application checks improve feedback, but invariants that must survive
> concurrent transactions require an authoritative database constraint.

## What you will learn

You will learn to:

- install the PostgreSQL persistence dependencies;
- wire SQLAlchemy through psycopg 3;
- understand why PostgreSQL is the production-reference backend;
- distinguish application validation from database enforcement;
- understand normalized Tag uniqueness;
- understand Tag-assignment uniqueness;
- understand persistence ownership foreign keys;
- understand why some cross-aggregate references are deliberately not foreign
  keys;
- understand concurrency races between independent Sessions;
- understand commit-time SQLSTATE translation;
- understand Unicode, timezone, Decimal, JSON and Custom Field round trips;
- understand live schema and index introspection;
- understand repository conformance on PostgreSQL;
- understand transaction rollback qualification;
- prepare for Alembic migrations.

## 1. PostgreSQL is the production-reference backend

PyCRMKit qualifies its SQLAlchemy persistence stack against a live PostgreSQL 17
service in CI.

PostgreSQL is not exposed as a new domain API. It is the production database
behind the same repository and Unit of Work contracts introduced earlier.

## 2. Install the PostgreSQL extra

~~~bash
pip install "pycrmkit[postgresql]"
~~~

The stable dependency group contains:

~~~text
SQLAlchemy >= 2.0, < 2.2
psycopg[binary] >= 3.2, < 3.4
~~~

## 3. PostgreSQL uses normal SQLAlchemy wiring

~~~python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

engine = create_engine(
    "postgresql+psycopg://crm:secret@localhost:5432/crm",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
~~~

The Unit of Work remains backend-neutral at the application boundary.

## 4. PostgreSQL sits below repository contracts

Application services continue to depend on repository protocols and UnitOfWork,
not on psycopg connections.

## 5. SQLAlchemy and PostgreSQL have different responsibilities

~~~text
SQLAlchemy
  |
  +--> persistence mapping
  +--> statements
  +--> Session lifecycle
  +--> transaction API

PostgreSQL
  |
  +--> durable storage
  +--> authoritative constraints
  +--> indexes
  +--> concurrency
  +--> SQLSTATE diagnostics
~~~

## 6. Application checks are not enough under concurrency

Suppose a repository checks whether normalized Tag name vip already exists.

Transaction A can see no row.

Transaction B can also see no row.

Both observations may be correct before either transaction commits.

## 7. The race window

~~~text
Transaction A                 Transaction B

find "vip" -> none            find "vip" -> none
      |                              |
      v                              v
INSERT "VIP"                  INSERT "vip"
      |                              |
      +---------- race --------------+
                    |
                    v
             PostgreSQL UNIQUE
~~~

Only the database can enforce the invariant across those independent
transactions.

## 8. Tag normalization is persisted explicitly

TagModel stores:

~~~text
name
normalized_name
~~~

For example:

~~~text
TagName("VIP") -> normalized_name = "vip"
TagName("vip") -> normalized_name = "vip"
~~~

## 9. PostgreSQL enforces normalized Tag uniqueness

The schema declares:

~~~text
uq_pycrmkit_tags_normalized_name
~~~

over:

~~~text
pycrmkit_tags.normalized_name
~~~

This protects the normalized domain key at the database boundary.

## 10. The repository still performs an early check

SQLAlchemyTagRepository calls find_by_normalized before adding a new Tag.

When an existing Tag is visible, the repository raises:

~~~text
DuplicateError
code = tag.duplicate
~~~

## 11. Early validation and database enforcement complement each other

The repository check gives fast, domain-friendly feedback.

The PostgreSQL unique constraint closes the race condition.

Neither layer makes the other unnecessary.

## 12. Tag assignment uniqueness is database-enforced

TagAssignmentModel declares a unique constraint over:

~~~text
tag_id
entity_kind
entity_id
~~~

named:

~~~text
uq_pycrmkit_tag_assignments_target
~~~

The same Tag cannot be assigned twice to the same entity target.

## 13. Assignment uniqueness also has a repository pre-check

The repository checks whether that tuple already exists before adding a new
assignment.

The pre-check is useful but PostgreSQL remains authoritative under concurrency.

## 14. Tag assignment has a persistence ownership foreign key

TagAssignmentModel.tag_id references:

~~~text
pycrmkit_tags.id
~~~

with:

~~~text
ON DELETE CASCADE
~~~

A persisted assignment therefore requires its parent Tag to exist.

## 15. Ownership foreign keys are intentional

PyCRMKit keeps database foreign keys when the relationship represents
persistence ownership or a structurally dependent child.

Examples include:

~~~text
Tag Assignment -> Tag
Contact Email -> Contact
Contact Phone -> Contact
Contact Address -> Contact
Organization child rows -> Organization
Pipeline child rows -> Pipeline
Communication child rows -> parent communication state
Webhook Delivery Attempt -> Webhook Delivery
~~~

## 16. Not every domain reference is persistence ownership

A typed ID pointing to another aggregate does not automatically imply that
PostgreSQL should enforce a foreign key.

That distinction was explicitly validated during the persistence release
candidate.

## 17. Lead cross-aggregate references are not ownership FKs

LeadModel persists contact_id and organization_id as indexed reference columns.

They are not database foreign keys requiring those aggregates to exist.

## 18. Opportunity references use the same approach

OpportunityModel persists contact_id and organization_id as indexed string
reference IDs without ownership FK enforcement.

## 19. Webhook Delivery subscription_id is a reference column

WebhookDeliveryModel.subscription_id remains persisted and indexed.

It is not an ownership foreign key in the stable aligned persistence model.

## 20. Why those FKs were removed

The reusable repository contracts do not require those referenced aggregates to
exist at the persistence layer.

A SQL backend must not silently introduce stronger preconditions than the
backend-neutral repository protocol.

## 21. Backend parity matters

A persistence adapter should preserve the same observable contract across:

~~~text
Memory
SQLite / SQLAlchemy
PostgreSQL / SQLAlchemy
~~~

Database-only restrictions that change repository behavior are contract
mismatches.

## 22. Reference columns still retain value

Removing a non-contractual FK does not remove the reference itself.

The column remains persisted, indexed, queryable and rehydrated into typed IDs.

## 23. Ownership FK violations are normalized

If PostgreSQL rejects an ownership relation because the parent does not exist,
it reports SQLSTATE:

~~~text
23503
~~~

PyCRMKit maps this to:

~~~text
RepositoryError
code = repository.foreign_key_violation
~~~

## 24. PostgreSQL SQLSTATE is the diagnostic boundary

PyCRMKit translates important PostgreSQL SQLSTATE values:

~~~text
23505 -> repository.duplicate
23503 -> repository.foreign_key_violation
23502 -> repository.not_null_violation
23514 -> repository.check_violation
40001 -> repository.serialization_failure
40P01 -> repository.deadlock
~~~

## 25. Unique violations become DuplicateError

SQLSTATE 23505 maps to:

~~~text
DuplicateError
code = repository.duplicate
~~~

The application does not need to catch psycopg-specific uniqueness exceptions.

## 26. Serialization failures are normalized

SQLSTATE 40001 maps to:

~~~text
RepositoryError
code = repository.serialization_failure
~~~

This provides a backend-neutral signal for application-level retry policy.

## 27. Deadlocks are normalized

SQLSTATE 40P01 maps to:

~~~text
RepositoryError
code = repository.deadlock
~~~

## 28. Error context is intentionally safe

Translated database errors can retain:

~~~text
sqlstate
constraint
table
column
~~~

when available.

They deliberately do not expose:

~~~text
SQL statement
bound parameters
payload values
~~~

## 29. Commit is the critical database error boundary

Many relational constraints become authoritative at flush or commit time.

SQLAlchemyUnitOfWork wraps session.commit and translates failures after rolling
the transaction back.

## 30. Failed commit clears staged events

~~~text
session.commit fails
        |
        v
session.rollback
        |
        v
pending events cleared
        |
        v
translated PyCRMKit error
~~~

No staged Domain Event is published.

## 31. Successful commit precedes event dispatch

~~~text
repository writes
      |
      v
PostgreSQL COMMIT
      |
      v
durable state
      |
      v
post-commit Domain Events
~~~

Subscriber failure after commit cannot undo the database transaction.

## 32. PostgreSQL qualification exercises independent Sessions

The concurrent Tag test uses two separate SQLAlchemy Sessions.

That matters because one Session cannot model two competing transactions.

## 33. The concurrency test synchronizes the race

The test creates:

~~~text
TagName("VIP")
TagName("vip")
~~~

and uses a Barrier so both workers reach the write boundary before either
commits.

## 34. Exactly one conflicting Tag survives

The expected outcomes are:

~~~text
committed
duplicate
~~~

After both transactions finish, one normalized vip Tag remains persisted.

## 35. This is stronger than a sequential duplicate test

Sequential duplicate detection proves:

~~~text
second transaction sees first commit
~~~

Concurrent qualification proves:

~~~text
both transactions may pass their pre-check
yet the invariant still survives
~~~

## 36. Live PostgreSQL schema introspection is part of qualification

The dedicated test inspects the database itself.

It verifies that PostgreSQL actually created the expected tables, constraints
and indexes.

## 37. Normalized Tag uniqueness is introspected

The live database must report:

~~~text
uq_pycrmkit_tags_normalized_name
~~~

## 38. Tag assignment uniqueness is introspected

The live database must report:

~~~text
uq_pycrmkit_tag_assignments_target
~~~

## 39. Webhook query index is introspected

The live database must report:

~~~text
ix_pycrmkit_webhook_delivery_subscription_event
~~~

## 40. PostgreSQL qualifies Unicode round trips

The persistence test stores values including:

~~~text
Zoë 東京
élève 東京
~~~

and verifies exact domain reload.

## 41. Unicode qualification includes JSON metadata

Contact metadata contains Unicode values and round-trips through the JSON
persistence representation.

## 42. Timezone-aware datetime round trips are qualified

The PostgreSQL test persists a UTC-aware datetime and verifies that the
rehydrated domain value equals the original.

## 43. Opportunity estimated value uses Numeric(19, 4)

OpportunityModel declares:

~~~text
estimated_value Numeric(19, 4)
~~~

This preserves the Decimal-oriented Sales contract.

## 44. Opportunity probability uses Numeric(7, 6)

Probability persistence uses:

~~~text
Numeric(7, 6)
~~~

The live qualification verifies values such as:

~~~text
Decimal("0.375000")
~~~

round-trip exactly.

## 45. PostgreSQL persistence does not convert sales values to float

The live test compares Decimal values after fresh reload.

This avoids binary floating-point loss in monetary and probability state.

## 46. JSON and Custom Fields are qualified live

The PostgreSQL persistence test stores a CustomFieldDefinition and
CustomFieldValue with JSON and Unicode content and verifies the exact domain
round-trip.

## 47. Fresh Session reload proves real persistence

The test commits in one Unit of Work and reloads in another.

This prevents SQLAlchemy's identity map from masking database persistence
problems.

## 48. Multi-repository rollback is qualified on PostgreSQL

The persistence release candidate includes PostgreSQL rollback coverage across
multiple repositories in one Unit of Work.

A failure before commit must not leave partial Contact or Organization state.

## 49. Repositories still never commit independently

~~~text
repository.save
        !=
database commit
~~~

Only SQLAlchemyUnitOfWork owns transaction commit.

## 50. Repository conformance runs on PostgreSQL

The Persistence Qualification workflow points:

~~~text
PYCRMKIT_SQLALCHEMY_TEST_URL
~~~

at the live PostgreSQL service and executes SQLAlchemy adapter contract tests
against it.

## 51. SQLite and PostgreSQL share observable contracts

~~~text
SQLite / SQLAlchemy
PostgreSQL / SQLAlchemy
        |
        v
same repository contract
~~~

Backend implementation differences should not leak as incompatible behavior.

## 52. PostgreSQL can expose mismatches SQLite misses

Production-reference qualification exposed cross-aggregate foreign keys that
were stronger than the repository contracts.

Live PostgreSQL testing therefore protects semantics, not only syntax.

## 53. Dedicated CI uses PostgreSQL 17

The workflow starts:

~~~text
postgres:17
~~~

and connects through:

~~~text
postgresql+psycopg://...
~~~

## 54. Live tests are explicitly marked

The PostgreSQL adapter suite uses pytest.mark.postgresql and requires:

~~~text
PYCRMKIT_TEST_POSTGRES_URL
~~~

When the environment variable is absent, the live tests are skipped.

## 55. The test database is reset between tests

The fixture truncates adapter tables with:

~~~text
TRUNCATE ... RESTART IDENTITY CASCADE
~~~

This gives deterministic test state while preserving the real schema.

## 56. pool_pre_ping belongs to infrastructure wiring

The documented PostgreSQL engine uses:

~~~python
pool_pre_ping=True
~~~

This validates pooled connections before reuse.

It is infrastructure configuration, not domain behavior.

## 57. Connection details stay outside the domain

The domain never knows the database host, database name, user, password, driver
or pool configuration.

Those belong to application composition.

## 58. Constraints should reflect stable contracts

A database constraint is appropriate when it protects a stable invariant that
must hold despite concurrent writers.

It should not be added merely because a column contains another aggregate's ID.

## 59. Ownership and reference are different concepts

~~~text
Ownership
  |
  +--> dependent persistence lifecycle
  +--> FK often appropriate

Reference
  |
  +--> typed identity link
  +--> independent aggregate lifecycle
  +--> FK may be too strong
~~~

## 60. Indexes support query contracts

Indexes support important paths such as normalized Tag lookup, Contact
normalized email/phone, status/owner filtering, reference IDs and Webhook
subscription/event queries.

Indexes are persistence optimizations, not domain rules.

## 61. Named constraints improve diagnostics

Stable names such as:

~~~text
uq_pycrmkit_tags_normalized_name
uq_pycrmkit_tag_assignments_target
~~~

make failures and migrations easier to reason about deterministically.

## 62. Business code catches PyCRMKit errors

Prefer:

~~~python
except DuplicateError:
    ...
~~~

rather than a psycopg-specific UniqueViolation exception.

## 63. Safe PostgreSQL diagnostics remain available

Operational code may inspect safe error context such as sqlstate and constraint
name while remaining independent of psycopg exception classes.

## 64. Retry policy remains an application decision

PyCRMKit normalizes serialization failures and deadlocks, but it does not decide
that every failed business operation is automatically safe to retry.

Retry safety depends on idempotency and transaction scope.

## 65. PostgreSQL does not own CRM business transitions

The database does not decide whether a Lead can convert, whether an Opportunity
can move stage, whether a Contact can archive or how merge conflicts resolve.

Those remain domain/application concerns.

## 66. PostgreSQL enforces persistence invariants

Its role includes:

~~~text
uniqueness
ownership integrity
not-null requirements
check constraints
durable transactions
concurrent conflict resolution
~~~

## 67. Typed IDs survive the database boundary

ORM models commonly store IDs as strings.

Repository mappers restore ContactId, OrganizationId, TagId, OpportunityId and
other domain ID types before returning objects.

## 68. JSON columns remain persistence representations

PostgreSQL JSON storage does not replace domain mapping.

Mappers still reconstruct metadata and typed Custom Field values.

## 69. Production-reference does not make Memory obsolete

Memory remains valuable for deterministic tests and local workflows.

SQLite remains useful for lightweight SQLAlchemy qualification.

PostgreSQL is the production-reference backend for relational durability and
concurrency.

## 70. create_all creates current schema only

PostgreSQL adapter tests may use:

~~~python
Base.metadata.create_all(engine)
~~~

for disposable databases.

This does not describe how an existing production database evolves between
versions.

## 71. Schema evolution belongs to Alembic

~~~text
current SQLAlchemy metadata
        |
        v
Alembic migration history
        |
        v
existing PostgreSQL database
~~~

That lifecycle is the subject of Chapter 25.

## 72. Persistence Qualification combines multiple layers

The dedicated workflow starts PostgreSQL 17 and validates:

~~~text
PostgreSQL adapter tests
stable facade persistence scenarios
repository conformance on PostgreSQL
migration chain
built-wheel persistence smoke
~~~

## 73. Stable CRM scenarios run on PostgreSQL

The persistence qualification traverses CRM Core, Customer Activity, Sales,
Communication, Events and Webhooks using durable PostgreSQL-backed state.

## 74. Migration tests also run against PostgreSQL

The persistence gate validates the migration chain on the same
production-reference database.

The next chapter studies that lifecycle in detail.

## 75. The built wheel is persistence-qualified

CI builds the wheel, creates a clean virtual environment, installs persistence
dependencies, applies packaged migrations and runs a PostgreSQL smoke scenario.

## 76. Why installed-wheel testing matters

Source-tree tests cannot prove that persistence code and migration assets are
correctly included in the artifact consumers install.

The clean-environment smoke validates the distributable package.

## 77. PostgreSQL is a compatibility gate

The goal is not merely:

~~~text
SQL executes
~~~

The goal is:

~~~text
stable CRM contract
      |
      v
same repository semantics
      |
      v
SQLAlchemy transactions
      |
      v
PostgreSQL durability and concurrency
~~~

## 78. Minimal production wiring

~~~python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit.storage.sqlalchemy import SQLAlchemyUnitOfWork

engine = create_engine(
    "postgresql+psycopg://crm:secret@localhost:5432/crm",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    contact = uow.contacts.get(contact_id)
    contact.source = "postgresql"
    uow.contacts.save(contact)
    uow.commit()
~~~

The application still manipulates Contact, not a PostgreSQL row object.

## 79. Three-layer invariant model

~~~text
Domain
  |
  +--> business validity

Repository
  |
  +--> early duplicate/conflict feedback
  +--> domain-friendly query semantics

PostgreSQL
  |
  +--> authoritative concurrent persistence constraints
~~~

## 80. Normalized Tag uniqueness across the layers

~~~text
Domain:
TagName normalizes "VIP" -> "vip"

Repository:
find_by_normalized("vip")
early duplicate detection

PostgreSQL:
UNIQUE(normalized_name)
authoritative under concurrent commits
~~~

## 81. Tag assignment across the layers

~~~text
Domain:
TagAssignment contains TagId + EntityReference

Repository:
duplicate-assignment pre-check

PostgreSQL:
FK(tag_id -> tag)
UNIQUE(tag_id, entity_kind, entity_id)
~~~

## 82. Opportunity Contact reference across the layers

~~~text
Domain:
Opportunity.contact_id is ContactId

Repository:
preserves typed reference semantics

PostgreSQL:
indexed reference column
no ownership FK requirement
~~~

The distinction is intentional.

## Common mistakes

### Treating application duplicate checks as concurrency-safe

Two transactions can pass the same pre-check before either commits.

### Removing database uniqueness because Python validates first

The unique constraint remains necessary for concurrent correctness.

### Catching psycopg exceptions in domain services

Use PyCRMKit persistence errors instead.

### Assuming every typed reference needs a foreign key

Typed identity and persistence ownership are not the same concept.

### Adding backend-only FKs that strengthen repository contracts

Supported adapters should preserve equivalent observable behavior.

### Publishing events before PostgreSQL commit

Events are post-commit side effects.

### Publishing events after failed commit

Failed commit rolls back and clears pending events.

### Converting Decimal values to float

Opportunity monetary values and probability use exact Numeric/Decimal
semantics.

### Qualifying PostgreSQL behavior only with SQLite

SQLite cannot prove PostgreSQL SQLSTATE, concurrency or live constraint
behavior.

### Reading through the same Session and calling it a durability test

Use a fresh Session to force database reload.

### Using create_all as production migration management

Alembic owns production schema evolution.

## Testing PostgreSQL persistence

Schema tests should cover:

~~~text
tables
named unique constraints
ownership foreign keys
indexes
reference columns
numeric precision and scale
~~~

Round-trip tests should cover:

~~~text
Unicode
timezone-aware datetime
Decimal
JSON metadata
Custom Fields
typed IDs
fresh-session hydration
~~~

Concurrency tests should cover:

~~~text
independent Sessions
synchronized conflicting writes
one successful commit
one DuplicateError
invariant preserved after race
~~~

Error-boundary tests should cover:

~~~text
SQLSTATE translation
safe diagnostic metadata
no SQL statement leakage
no parameter leakage
rollback after failed commit
no event publication
~~~

Contract tests should cover:

~~~text
same repository behavior as Memory/SQLite
no backend-only preconditions
deterministic ordering
exact pagination
lifecycle semantics
typed errors
~~~

## What you learned

You can now explain:

- why PostgreSQL is the production-reference backend;
- how psycopg fits below SQLAlchemy;
- repository pre-check versus database constraint;
- normalized Tag uniqueness;
- Tag-assignment uniqueness;
- concurrent uniqueness races;
- ownership FKs versus cross-aggregate references;
- SQLSTATE normalization;
- safe database diagnostics;
- exact Numeric/Decimal persistence;
- Unicode, timezone and JSON round trips;
- live schema/index introspection;
- PostgreSQL repository conformance;
- multi-repository rollback qualification;
- installed-wheel PostgreSQL qualification;
- why migration history is a separate concern.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter      ✅
23 SQLAlchemy          ✅
24 PostgreSQL          ✅
25 Migrations          ← NEXT
~~~

The persistence architecture now reaches the production-reference database:

~~~text
Domain / Application
        |
        v
Repository + UnitOfWork
        |
        v
SQLAlchemy Adapter
        |
        v
PostgreSQL
~~~

## Next

The next chapter is **25 - Migrations**.

The stack becomes:

~~~text
SQLAlchemy Models
        |
        +--> current metadata
        |
        v
Alembic migration history
        |
        v
PostgreSQL schema versions
~~~

The next learning question is:

> How does PyCRMKit evolve a production PostgreSQL schema across released
> versions without losing data, drifting from SQLAlchemy metadata or rewriting
> historical migrations?
