# SQLAlchemy

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 22 established the persistence contracts with the Memory adapter. The
next step is to keep those application-visible semantics while replacing
in-process state with a relational persistence implementation.

The stable architecture is:

~~~text
Domain / Application Services
          |
          v
Repository + UnitOfWork contracts
          |
          v
SQLAlchemy repositories
          |
          v
Domain <-> ORM mappers
          |
          v
SQLAlchemy Session
          |
          v
Relational database
~~~

The critical design rule is:

> SQLAlchemy is an adapter detail. Domain entities are never ORM models, and
> normal PyCRMKit APIs do not expose SQLAlchemy Sessions or query objects.

## What you will learn

You will learn to:

- install the optional SQLAlchemy adapter;
- understand the adapter-owned declarative Base;
- understand deterministic metadata naming;
- distinguish domain entities from ORM persistence models;
- understand explicit bidirectional mapping;
- understand normalized persistence models for value objects;
- understand session-scoped repository adapters;
- understand why repositories never commit independently;
- understand SQLAlchemyUnitOfWork;
- preserve commit/rollback semantics from the Memory adapter;
- understand exact pagination and deterministic ordering;
- understand backend-safe error translation;
- understand why SQLite is useful for adapter qualification but not the
  production-reference backend;
- prepare for PostgreSQL in the next chapter.

## 1. SQLAlchemy is optional

PyCRMKit core has no mandatory SQLAlchemy dependency.

Install the adapter with:

~~~bash
pip install "pycrmkit[sqlalchemy]"
~~~

The declared stable dependency range is:

~~~text
SQLAlchemy >= 2.0, < 2.2
~~~

Applications that never import the SQLAlchemy persistence package do not need
SQLAlchemy installed.

## 2. Dependency direction remains domain-first

The dependency direction is:

~~~text
Domain
  |
  v
Repository contracts
  |
  v
Unit of Work
  |
  v
SQLAlchemy adapter
  |
  v
Database
~~~

The domain layer does not depend on SQLAlchemy.

## 3. Domain entities are not ORM models

A PyCRMKit Contact is a domain aggregate.

A ContactModel is a SQLAlchemy persistence representation.

They are deliberately separate types.

~~~text
Contact
  !=
ContactModel
~~~

This keeps ORM concerns out of domain construction, validation and behavior.

## 4. ORM models live inside the adapter package

Persistence models are defined under:

~~~text
pycrmkit.storage.sqlalchemy.models
~~~

Examples include:

~~~text
ContactModel
OrganizationModel
RelationshipModel
ActivityModel
TaskModel
LeadModel
OpportunityModel
PipelineModel
TagModel
CustomFieldDefinitionModel
TimelineEntryModel
AuditEntryModel
WebhookSubscriptionModel
WebhookDeliveryModel
~~~

These classes belong to the persistence adapter.

## 5. The adapter owns its declarative Base

PyCRMKit defines:

~~~python
from pycrmkit.storage.sqlalchemy import Base
~~~

Base is the SQLAlchemy DeclarativeBase used only by the adapter.

Domain classes do not inherit from it.

## 6. Metadata naming is deterministic

The SQLAlchemy adapter configures a naming convention for indexes, unique
constraints, checks, foreign keys and primary keys.

Conceptually:

~~~text
ix_<table>_<column>
uq_<table>_<column>
ck_<table>_<column>
fk_<table>_<column>_<referred_table>
pk_<table>
~~~

Deterministic constraint names matter for qualification and later migrations.

## 7. Timestamped persistence models share a mixin

TimestampedModelMixin defines persistence columns for:

~~~text
created_at
updated_at
~~~

using timezone-aware SQLAlchemy DateTime columns.

The mixin represents persistence structure, not domain inheritance.

## 8. Contact persistence is normalized

A Contact is not stored as one JSON blob.

The adapter uses:

~~~text
pycrmkit_contacts
pycrmkit_contact_emails
pycrmkit_contact_phones
pycrmkit_contact_addresses
~~~

The Contact row stores aggregate-level fields while repeated value objects use
ordered child tables.

## 9. Child records preserve order explicitly

Contact emails, phones and addresses persist a position column.

Hydration orders by position and then database row ID.

That preserves the ordered tuple semantics of the domain aggregate.

## 10. Normalized values are queryable

ContactEmailModel stores both:

~~~text
value
normalized
~~~

and normalized is indexed.

The repository can therefore query by normalized email without loading every
Contact into Python.

## 11. ORM representation is not the public API

Application code should receive:

~~~text
Contact
Organization
Opportunity
TimelineEntry
...
~~~

not:

~~~text
ContactModel
OrganizationModel
OpportunityModel
...
~~~

Repositories perform the conversion.

## 12. Mapping is an explicit boundary

The adapter defines the SQLAlchemyMapper protocol:

~~~python
class SQLAlchemyMapper(Protocol[DomainT, ModelT]):
    def to_model(self, domain: DomainT) -> ModelT:
        ...

    def to_domain(self, model: ModelT) -> DomainT:
        ...
~~~

The important idea is explicit bidirectional conversion.

## 13. FunctionalMapper is available

FunctionalMapper provides a small generic implementation around two callables:

~~~text
domain -> model
model  -> domain
~~~

The larger bounded-context mapper module also contains concrete conversion
functions for the stable persistence models.

## 14. Contact mapping is explicit

Contact persistence uses dedicated conversion logic.

The mapper translates:

~~~text
typed ContactId -> string database ID
ContactStatus   -> stable string value
owner EntityId  -> string or null
metadata        -> JSON mapping
archived_at     -> persistence datetime
~~~

and reconstructs the typed domain equivalents when reading.

## 15. Typed IDs are restored

Hydration uses domain ID parsers such as:

~~~text
ContactId.parse(...)
OrganizationId.parse(...)
TagId.parse(...)
~~~

The result returned by a repository therefore contains the same domain ID
types expected from the Memory adapter.

## 16. EntityReference type information is preserved

Timeline and other reference-oriented persistence needs more than a raw UUID.

The mapper can restore the concrete UUIDId subtype so EntityReference equality
survives a database round-trip.

This persistence detail was explicitly qualified during the 0.6.x line.

## 17. Datetime hydration is normalized

Database drivers can differ in how timezone-aware values are returned.

The mapper normalizes returned datetimes to UTC-aware domain values.

SQLite naive datetime results are explicitly handled by the adapter mapper.

## 18. Custom Field values require tagged persistence

Custom Field values may contain types that are not directly JSON-safe, including:

~~~text
Decimal
datetime
date
EntityReference
tuple
~~~

The mapper encodes supported values into tagged JSON envelopes and decodes them
back into their domain Python types.

## 19. Repository adapters are session-scoped

A SQLAlchemy repository receives one SQLAlchemy Session:

~~~python
repository = SQLAlchemyContactRepository(session)
~~~

That Session is the repository's persistence context.

## 20. Repository methods return domain objects

For example:

~~~python
contact = repository.get(contact_id)
~~~

returns Contact, not ContactModel.

The SQLAlchemy model remains behind the adapter boundary.

## 21. get and find preserve repository contracts

SQLAlchemyContactRepository follows the same visible behavior as the Memory
adapter:

~~~text
get(missing)
-> NotFoundError

find(missing)
-> None
~~~

The backend change does not change the domain repository contract.

## 22. save performs persistence mapping

For a Contact, save:

~~~text
load existing ContactModel if present
        |
        v
map aggregate fields into model
        |
        v
add model if new
        |
        v
replace persisted emails
replace persisted phones
replace persisted addresses
~~~

The repository reconstructs the aggregate's child persistence rows from current
domain state.

## 23. save does not commit

This is a central rule.

SQLAlchemy repository methods deliberately do not call:

~~~python
session.commit()
~~~

Transaction ownership belongs to SQLAlchemyUnitOfWork.

## 24. Why repositories must not commit independently

A business operation can touch:

~~~text
Contact
Organization
Relationship
AuditEntry
Tag assignment
Custom Field
~~~

If one repository committed independently, the application could not guarantee
atomic cross-repository behavior.

## 25. Search is pushed into SQL

SQLAlchemyContactRepository builds a SELECT statement and adds filters for:

~~~text
archive visibility
status
normalized email
normalized phone
name
owner
source
~~~

Filtering occurs in the database adapter rather than by loading the entire
table into application memory.

## 26. Deterministic ordering is preserved

Contact search orders by:

~~~text
created_at ASC
id ASC
~~~

before offset/limit pagination.

This mirrors the observable contract established by the Memory adapter.

## 27. Pagination computes the filtered total

The shared page_models helper creates:

~~~text
COUNT(filtered statement)
SELECT filtered statement OFFSET ... LIMIT ...
~~~

and returns a domain Page containing:

~~~text
items
limit
offset
total
~~~

## 28. Hydration can require child queries

A Contact row alone is not a complete Contact aggregate.

The repository also loads ordered email, phone and address rows, then invokes
the domain mapper to reconstruct the aggregate.

## 29. SQLAlchemyUnitOfWork owns one Session

A Unit of Work obtains one Session from its SessionFactory.

Every SQLAlchemy repository exposed by that UoW is bound to that exact Session.

~~~text
SQLAlchemyUnitOfWork
        |
        +--> contacts ---------+
        +--> organizations ----+
        +--> relationships ----+
        +--> activities -------+--> same Session
        +--> audit ------------+
        +--> tags -------------+
        +--> custom_fields ----+
        +--> ... --------------+
~~~

## 30. One Session means one transaction boundary

Because all repositories share one Session, their pending writes participate in
the same database transaction.

That provides the SQL equivalent of the shared working snapshot from the Memory
adapter.

## 31. Entering the UoW creates the Session

On context entry:

~~~text
session_factory()
      |
      v
Session
      |
      v
bind all repositories
~~~

The Unit of Work becomes active only inside this scope.

## 32. Access outside the UoW is rejected

Attempting to use repositories or commit before context entry raises:

~~~text
InvalidStateError
code = sqlalchemy.uow.not_active
~~~

## 33. Explicit commit remains required

~~~python
with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    uow.contacts.save(contact)
    uow.commit()
~~~

The context manager does not auto-commit.

## 34. Exit without commit rolls back

If the context exits while its transaction is still open and uncommitted:

~~~text
session.rollback()
session.close()
~~~

are applied by the Unit of Work lifecycle.

## 35. Exceptions roll back pending state

An exception before successful commit causes the open SQLAlchemy transaction to
roll back during context exit.

## 36. Explicit rollback keeps the UoW usable

uow.rollback():

~~~text
session.rollback()
clear pending events
keep UoW active
~~~

A caller may continue with new writes and later commit them within the same
Unit of Work scope.

## 37. Second commit is rejected

Once a transaction has committed, a repeated commit raises:

~~~text
InvalidStateError
code = sqlalchemy.uow.already_committed
~~~

## 38. Events are staged until database commit succeeds

SQLAlchemyUnitOfWork keeps Domain Events in memory while the database
transaction is pending.

Only after session.commit succeeds are the staged events published.

## 39. Database commit precedes event publication

The sequence is:

~~~text
repository writes
      |
      v
stage events
      |
      v
session.commit()
      |
      v
mark transaction closed
      |
      v
publish events
~~~

A subscriber therefore observes committed database state.

## 40. Subscriber failure does not undo the database commit

If a synchronous event handler raises after successful commit, the database
transaction is already committed.

The subscriber exception can propagate, but committed persistence is not rolled
back.

## 41. SQLAlchemy errors are translated at the boundary

Commit-time SQLAlchemy/driver failures are caught by the Unit of Work.

The adapter rolls back and translates them into PyCRMKit public persistence
errors.

## 42. Error translation avoids leaking SQL details

The safe diagnostic context may include:

~~~text
SQLSTATE
constraint name
table name
column name
~~~

It does not expose SQL text or bound parameter values.

## 43. PostgreSQL uniqueness maps to DuplicateError

When a PostgreSQL IntegrityError reports SQLSTATE:

~~~text
23505
~~~

the adapter maps it to:

~~~text
DuplicateError
code = repository.duplicate
~~~

## 44. Other PostgreSQL error codes are normalized

The adapter also defines stable translations for:

~~~text
23503 -> repository.foreign_key_violation
23502 -> repository.not_null_violation
23514 -> repository.check_violation
40001 -> repository.serialization_failure
40P01 -> repository.deadlock
~~~

Other SQLAlchemy failures become repository.backend_error.

## 45. The domain never catches SQLAlchemyError directly

Application/domain code should work with the public PyCRMKit error hierarchy.

Backend-specific exceptions are an adapter concern.

## 46. Local SQLite setup

For local experimentation:

~~~python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pycrmkit.storage.sqlalchemy import (
    Base,
    SQLAlchemyUnitOfWork,
)

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
)

Base.metadata.create_all(engine)

SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
)
~~~

This is suitable for learning and adapter tests.

## 47. create_all is not the production schema lifecycle

Base.metadata.create_all is useful for:

~~~text
tests
local experiments
isolated examples
~~~

Production schema evolution is handled through Alembic migrations, covered in a
later chapter.

## 48. Basic persisted Contact example

~~~python
with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    contact = ContactService(
        uow.contacts,
        clock=clock,
    ).create(
        first_name="Ada",
        last_name="Lovelace",
    )
    uow.commit()

with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    loaded = uow.contacts.get(contact.id)

assert loaded == contact
~~~

The caller works with Contact throughout.

## 49. Atomic multi-repository example

~~~python
with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    contact = ContactService(
        uow.contacts,
        clock=clock,
    ).create(
        first_name="Ada",
        last_name="Lovelace",
    )
    organization = OrganizationService(
        uow.organizations,
        clock=clock,
    ).create(
        legal_name="Analytical Engines Ltd",
    )
    uow.commit()
~~~

Both repository writes share one Session and one transaction.

## 50. Rollback example

~~~python
with SQLAlchemyUnitOfWork(SessionLocal) as uow:
    contact = ContactService(
        uow.contacts,
        clock=clock,
    ).create(
        display_name="Discarded",
    )
    uow.rollback()

    assert uow.contacts.find(contact.id) is None
~~~

The UoW remains active after rollback.

## 51. Repository contract parity matters

The SQLAlchemy adapters are exercised with reusable repository contract suites
also used to define Memory behavior.

That means applications should observe the same key semantics across adapters:

~~~text
typed entities
NotFound behavior
normalized filters
deterministic ordering
exact pagination
archive/lifecycle behavior
idempotent history where required
~~~

## 52. Backend parity does not mean implementation parity

Memory and SQLAlchemy use different mechanics:

~~~text
Memory
  -> deepcopy working state
  -> dictionaries
  -> publish cloned state

SQLAlchemy
  -> Session
  -> SQL statements
  -> database transaction
~~~

The important goal is equivalent application-visible contracts.

## 53. SQLAlchemy models may contain persistence-only structure

Examples include:

~~~text
surrogate integer child-row IDs
position columns
normalized query columns
foreign keys
indexes
JSON persistence columns
constraint names
~~~

These do not need equivalents in domain entities.

## 54. Domain objects may contain richer types

The mapper is responsible for reconstructing:

~~~text
typed UUID IDs
Enums
Value Objects
EntityReference
Decimal
datetime/date
immutable tuples
metadata mappings
~~~

from persistence representations.

## 55. ORM relationships are not required to define domain relationships

PyCRMKit can model relational persistence using explicit queries and mapper
logic without making domain behavior depend on SQLAlchemy relationship objects.

The domain's Relationship aggregate remains its own concept.

## 56. Session lifetime belongs to the UoW

Application services should not hold a Session globally.

The Session is created for the Unit of Work scope and closed on exit.

## 57. Repositories are unbound after UoW exit

SQLAlchemyUnitOfWork removes its repository references and closes the Session
when the context ends.

Repository access through that Unit of Work is no longer valid afterward.

## 58. expire_on_commit=False is useful in the documented wiring

The official examples construct sessionmaker with:

~~~python
expire_on_commit=False
~~~

This keeps SQLAlchemy persistence models from being automatically expired after
commit inside the adapter wiring.

Application code still works with domain objects, not those models.

## 59. SQLite is qualification infrastructure, not the production reference

The 0.6.0a2 repository adapter milestone qualified the repository layer using
isolated SQLite Sessions.

PostgreSQL production-reference qualification was deliberately a later
milestone.

## 60. Why PostgreSQL still needs its own chapter

SQLite adapter tests do not prove PostgreSQL-specific behavior such as:

~~~text
database constraint enforcement
concurrent uniqueness races
PostgreSQL SQLSTATE translation
production-reference transaction behavior
PostgreSQL-specific schema qualification
~~~

Those are covered by the next persistence layer.

## Common mistakes

### Making domain entities inherit from Base

Domain entities must remain ORM-neutral.

### Returning ContactModel from a repository

Repositories return Contact domain entities.

### Passing Session into domain services

Session belongs to the SQLAlchemy adapter/UoW boundary.

### Calling commit inside repository save

Transaction ownership belongs to SQLAlchemyUnitOfWork.

### Treating Base.metadata.create_all as production migration management

It is for tests and local experimentation; Alembic owns production evolution.

### Assuming SQLite proves PostgreSQL behavior

It proves adapter semantics in an isolated relational backend, not the full
production-reference database contract.

### Depending on ORM model object identity

Application code should depend on domain equality and repository semantics.

### Catching SQLAlchemyError in domain code

Backend failures should be translated into PyCRMKit persistence errors.

### Exposing SQL or bound values in error context

The adapter deliberately limits diagnostic metadata to safe fields.

### Reusing a Unit of Work after commit for new transaction work

A committed SQLAlchemyUnitOfWork transaction is closed; open a fresh UoW.

## Testing SQLAlchemy persistence

Foundation tests should cover:

~~~text
optional dependency boundary
Base metadata
constraint naming
model table definitions
domain/ORM mapper round trips
typed ID restoration
datetime normalization
Custom Field typed-value encoding
~~~

Repository tests should cover:

~~~text
reusable repository contracts
normalized queries
deterministic ordering
exact pagination
archive/lifecycle semantics
history/idempotency rules
~~~

Unit of Work tests should cover:

~~~text
one shared Session
atomic multi-repository commit
uncommitted rollback
exception rollback
explicit rollback
continue-after-rollback
event staging
post-commit event dispatch
second commit rejection
~~~

Persistence boundary tests should cover:

~~~text
backend error translation
safe diagnostic context
no SQL/parameter leakage
~~~

## What you learned

You can now explain:

- why SQLAlchemy is optional;
- why domain entities are not ORM models;
- adapter-owned Base and metadata;
- normalized persistence models;
- explicit domain/ORM mapping;
- typed-ID and datetime rehydration;
- Custom Field persistence encoding;
- session-scoped repositories;
- repository contract parity with Memory;
- exact SQL-backed pagination;
- SQLAlchemyUnitOfWork transaction ownership;
- explicit commit/rollback;
- post-commit event semantics;
- backend-safe error translation;
- the role and limits of SQLite qualification.

## LEVEL 6 in progress

The Persistence & Integrations learning path now contains:

~~~text
22 Memory Adapter      ✅
23 SQLAlchemy          ✅
24 PostgreSQL          ← NEXT
~~~

We have moved from:

~~~text
Repository contract
      |
      v
in-process reference adapter
~~~

to:

~~~text
Repository contract
      |
      v
SQLAlchemy adapter
      |
      v
relational persistence
~~~

without changing the domain-facing persistence contract.

## Next

The next chapter is **24 - PostgreSQL**.

The architecture will become:

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
SQLAlchemy Session
        |
        v
PostgreSQL
~~~

The next learning question is:

> Which persistence guarantees must move from application-level checks into
> PostgreSQL constraints and transactional behavior when concurrent real-world
> workloads are introduced?
