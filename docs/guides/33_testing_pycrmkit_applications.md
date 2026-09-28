# Testing PyCRMKit Applications

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter begins **LEVEL 7 - Production Applications**.

LEVEL 6 explained framework mechanics and integration boundaries. LEVEL 7 changes perspective:

> You are now building and qualifying an application that depends on PyCRMKit.

The testing question is no longer only whether PyCRMKit works. It becomes whether your application composes PyCRMKit correctly across business rules, persistence, HTTP, migrations, security and the deployable artifact.

A practical test pyramid is:

~~~text
                     Production E2E
                         /\
                        /  \
               PostgreSQL / HTTP
                   /          \
             adapter contracts
                /                \
          facade / application flows
             /                    \
        domain + Memory tests
       /____________________________\
~~~

The central rule is:

> Use the cheapest test that can prove the behavior, but keep a smaller set of real-adapter and real-production-boundary tests for behavior Memory cannot prove.

## What you will learn

You will learn to:

- understand the PyCRMKit test layers;
- use Memory for fast business tests;
- test facade workflows rather than implementation details;
- use FixedClock and deterministic context;
- test Domain Events, Audit and Timeline without infrastructure;
- test the same application behavior across Memory and SQLAlchemy;
- reuse repository contracts across adapters;
- distinguish SQLite adapter tests from PostgreSQL qualification;
- mark live PostgreSQL tests explicitly;
- reset and migrate ephemeral PostgreSQL databases;
- test migration state and drift;
- test FastAPI and DRF boundaries;
- test persistence across restart;
- test rollback and post-commit behavior;
- test security/privacy invariants;
- test the installed artifact rather than only source checkout;
- design an application CI pyramid.

## 1. Test application behavior first

Application tests should focus on observable business behavior.

Example:

~~~text
Given an active Contact
When a follow-up Task is created
Then the Task references the Contact
And task.created is emitted
And Audit uses the expected correlation
~~~

This is more valuable than asserting MemoryStore internals or mapper implementation details from application-level tests.

## 2. Five useful test layers

A practical application suite can be organized as:

~~~text
Layer 1  Domain / pure business tests
Layer 2  Facade / application tests with Memory
Layer 3  Adapter / persistence integration tests
Layer 4  HTTP + database E2E tests
Layer 5  Deployment-artifact / production qualification
~~~

Each layer answers a different question.

## 3. Layer 1 - pure domain tests

Pure domain tests should avoid infrastructure.

Examples:

~~~text
Contact value-object normalization
Task lifecycle transition
Pipeline transition policy
Money / Decimal behavior
Dedup scoring
Merge conflict policy
Webhook retry-policy calculation
~~~

These tests should not create a database merely to validate a Value Object.

## 4. Layer 2 - facade tests with Memory

Memory is the best default backend for most application workflow tests.

Example:

~~~python
crm = CRM.memory(
    webhook_auto_delivery=False,
)

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)

task = crm.tasks.create(
    title="Follow up",
    references=(
        EntityReference("contact", contact.id),
    ),
)
~~~

This exercises facade, domain services, Unit of Work semantics, repositories, events, audit and Timeline without database setup.

## 5. Why Memory is useful

Memory provides:

~~~text
fast startup
no external service
deterministic state
explicit transactions
same public CRM facade
same repository protocols
same Domain Events
same Audit APIs
~~~

It is ideal for business behavior, state transitions, error codes, context propagation, event subscriptions, Audit assertions and Timeline assertions.

## 6. What Memory cannot prove

Memory cannot prove:

~~~text
PostgreSQL constraints
SQL isolation
deadlocks
serialization failures
database concurrency
SQLAlchemy mapping correctness
database type round trips
Alembic migrations
Django migrations
restart durability
real SQL pagination
~~~

A complete application suite should therefore use Memory heavily, but not exclusively.

## 7. Make time deterministic

Prefer FixedClock for time-dependent tests.

~~~python
clock = FixedClock(
    datetime(
        2026,
        9,
        28,
        10,
        0,
        tzinfo=UTC,
    )
)

crm = CRM.memory(
    clock=clock,
    webhook_auto_delivery=False,
)
~~~

Advance the clock explicitly when the scenario needs time to move.

## 8. Avoid sleep-based tests

Do not wait for wall-clock time merely to prove timestamp ordering.

Prefer:

~~~text
FixedClock
advance
explicit expected timestamp
~~~

This makes tests faster and less flaky.

## 9. Bind operation context explicitly

Where traceability matters:

~~~python
crm = CRM.memory(
    webhook_auto_delivery=False,
).with_context(
    actor_id="test-user",
    correlation_id="test-follow-up-001",
)
~~~

Then assert actor/correlation on DomainEvent and AuditEntry.

## 10. Test through the public facade by default

If production code calls crm.contacts, crm.tasks or crm.leads, application tests should normally use those same public entry points.

This reduces the risk of testing a composition different from production.


## 11. Test application services directly when they own behavior

If your application adds a service above PyCRMKit, test that service directly.

~~~text
SalesFollowUpService
      |
      v
CRM facade
      |
      v
PyCRMKit
~~~

The unit under test is your application service. PyCRMKit remains a dependency.

## 12. Assert observable outcomes

Good assertions include:

~~~text
returned domain state
persisted state
stable error code
event type
event context
Audit action
Timeline entry
HTTP status
HTTP error code
~~~

Avoid private implementation assertions unless the test explicitly targets an adapter.

## 13. Fast workflow example

A useful Memory test can prove:

~~~text
Contact created
      |
      v
Task created for Contact
      |
      v
Task completed
      |
      +--> status completed
      +--> Timeline contains task.created/task.completed
      +--> Audit uses one correlation
      +--> events published
~~~

No PostgreSQL container is needed for this business scenario.

## 14. Capture events synchronously

InProcessEventBus is synchronous.

~~~python
events = []

crm.events.subscribe(
    "task.completed",
    events.append,
)
~~~

After the command returns, the event can be asserted directly.

## 15. Disable automatic webhooks unless needed

Most business tests should use:

~~~python
CRM.memory(
    webhook_auto_delivery=False,
)
~~~

Webhook delivery belongs in focused webhook integration/security tests.

## 16. Assert Audit through its public API

If a workflow must be auditable:

~~~python
trace = crm.audit.by_correlation(
    "test-follow-up-001"
)
~~~

Assert actions and safe metadata rather than private repository storage.

## 17. Test Timeline selectively

Timeline is a selective read model.

Do not assume every DomainEvent appears there.

Assert documented Activity, Task and Email lifecycle projections when relevant.

## 18. Assert stable error codes

Prefer:

~~~text
error.code == "contact.archived"
~~~

over parsing human message text.

Stable codes are the machine-readable application contract.

## 19. Repository contract tests prevent adapter drift

If your application implements a custom repository adapter, use a reusable behavioral suite.

PyCRMKit itself follows this model:

~~~text
ContactRepositoryContract
         |
         +--> MemoryContactRepository
         +--> SQLAlchemyContactRepository
         +--> custom adapter
~~~

## 20. Contracts test semantics, not storage mechanics

A Contact repository contract qualifies behaviors such as:

~~~text
save and get
find missing -> None
get missing -> NotFoundError
save replaces state
deterministic pagination
normalized email search
archive visibility
~~~

Table names and SQL strings belong in adapter-specific tests, not the generic repository contract.

## 21. Memory has adapter-specific copy-isolation tests

PyCRMKit separately verifies that:

~~~text
mutating source object after save
does not mutate stored state

mutating loaded object without save
does not mutate stored state
~~~

Those are Memory-specific guarantees.

## 22. SQLAlchemy contracts can use SQLite for speed

Reusable SQLAlchemy repository tests can run on SQLite for mapper, Session and repository semantics.

This is useful for:

~~~text
mapper behavior
protocol conformance
transaction behavior
basic relational persistence
~~~

## 23. SQLite is not PostgreSQL qualification

SQLite cannot prove:

~~~text
PostgreSQL SQLSTATE
concurrent UNIQUE conflicts
production dialect behavior
PostgreSQL constraints
PostgreSQL migration chain
~~~

Keep those in a dedicated live PostgreSQL layer.

## 24. Mark live PostgreSQL tests explicitly

PyCRMKit declares the strict pytest marker:

~~~text
postgresql
~~~

Live database tests use pytest.mark.postgresql.

## 25. Use an explicit PostgreSQL test URL

The stable test environment uses:

~~~text
PYCRMKIT_TEST_POSTGRES_URL
~~~

Optional local tests can skip when it is absent.

A CI job claiming PostgreSQL qualification should always provide it.

## 26. Use an isolated disposable database

Destructive qualification commonly resets:

~~~text
DROP SCHEMA IF EXISTS public CASCADE
CREATE SCHEMA public
~~~

Only do this against a dedicated test database.

Never point such fixtures at production.

## 27. Migrate before production-like database tests

Prefer:

~~~text
empty schema
      |
      v
migration command
      |
      v
application test
~~~

Production migration qualification should not use Base.metadata.create_all as a substitute.

## 28. Migration tests answer a different question

Repository tests answer:

> Can this adapter persist and reload domain state?

Migration tests answer:

> Can a deployed database safely reach the required schema history?

Both matter.

## 29. Stable Alembic head

The stable PyCRMKit SQLAlchemy/Alembic head is:

~~~text
0003
~~~

Applications relying on packaged PyCRMKit migrations should validate the deployed revision where operationally important.

## 30. Test schema drift where relevant

PyCRMKit qualification compares migrated PostgreSQL schema against ORM metadata.

Applications owning additional tables should consider equivalent drift checks for their own schema.

## 31. Test historical upgrades

Important migration scenarios include:

~~~text
fresh database -> head
previous deployed revision -> head
data survives upgrade
head reports expected revision
model/migration drift empty
~~~

Fresh-install testing alone is insufficient for long-lived production databases.

## 32. FastAPI tests can stay fast with Memory

FastAPI TestClient can exercise a real HTTP boundary while CRM storage stays in-memory.

~~~text
HTTP request
      |
      v
FastAPI router
      |
      v
Pydantic validation
      |
      v
CRM.memory()
~~~

This is an effective middle layer between facade tests and PostgreSQL E2E.

## 33. HTTP tests should assert transport contracts

Useful assertions include:

~~~text
path
method
status
response schema
pagination shape
error response code
request validation
actor/correlation propagation
OpenAPI path
~~~

## 34. Do not make every HTTP test a database test

Routing, serialization and validation usually do not need real PostgreSQL.

Use Memory for broad HTTP integration coverage, then maintain a smaller PostgreSQL-backed E2E suite.

## 35. Real FastAPI PostgreSQL E2E should prove restart durability

PyCRMKit's reference test follows:

~~~text
reset DB
      |
migrate
      |
create app A
      |
HTTP write journey
      |
close app A
      |
create app B
      |
HTTP read previously written state
~~~

The second application instance proves durability beyond process-local state.

## 36. Test health and OpenAPI in production composition

The reference FastAPI E2E also verifies health and OpenAPI endpoints.

Deployability includes:

~~~text
application startup
database reachability
versioned OpenAPI
expected route registration
~~~

## 37. Use representative E2E journeys

One meaningful cross-layer journey can cover:

~~~text
create Contact
create Organization
create Relationship
log Activity
create/complete Task
read Timeline
verify 404 contract
restart
verify persistence
~~~

Do not reproduce every unit edge case through HTTP.

## 38. Django also needs layered testing

A Django application can separate:

~~~text
repository/model tests
migration tests
DjangoTransactionBridge tests
DRF tests
PostgreSQL reference E2E
installed-artifact E2E
~~~

## 39. Test Django migration/model drift

PyCRMKit's Django PostgreSQL workflow runs migration application plus:

~~~text
manage.py makemigrations pycrmkit_crm --check --dry-run
~~~

A consuming Django application should apply the same idea to its own models.

## 40. Test optional dependency boundaries

PyCRMKit qualifies combinations including:

~~~text
core
sqlalchemy
postgresql
migrations
fastapi
django
drf
email
resend
fastapi + postgresql + migrations
django + drf + postgresql
~~~

Applications with multiple deployment profiles should similarly test the profiles they claim to support.


## 41. Test source checkout and installed artifact separately

Source tests can pass while packaging is broken.

Typical packaging failures include:

~~~text
missing package data
missing migration files
bad entry point
undeclared dependency
source-path shadowing
~~~

An installed-wheel test catches these failures.

## 42. Clear PYTHONPATH for artifact qualification

PyCRMKit clean-wheel qualification explicitly clears PYTHONPATH.

This helps prove imports come from the installed distribution rather than the repository checkout.

## 43. Test the artifact you deploy

PyCRMKit verifies both wheel and sdist.

A deployable application may instead qualify:

~~~text
wheel
container image
zip bundle
serverless artifact
~~~

The important rule is to test the same artifact that production will execute.

## 44. Inspect required package assets

PyCRMKit explicitly checks that migration files, py.typed and package metadata are present in the wheel.

Applications should similarly check runtime-critical assets such as:

~~~text
migrations
templates
static files
configuration schemas
entry points
~~~

## 45. Security regression should be a dedicated layer

Security/privacy invariants deserve focused tests.

Examples:

~~~text
error redaction
secret-safe repr
event PII minimization
webhook HMAC
replay freshness
unsafe webhook URLs
archive mutation guard
merge provenance
~~~

## 46. Run security checks against the installed artifact

PyCRMKit runs tests/security twice:

~~~text
source checkout
built wheel in clean environment
~~~

This protects against packaging regressions in hardening code.

## 47. Performance tests are regression guardrails

PyCRMKit baseline covers:

~~~text
Contact creation
Contact search
Timeline retrieval
bulk import
repository pagination
event publication
~~~

The published budgets are release guardrails, not production SLAs.

## 48. Do not turn CI microbenchmarks into latency promises

Production performance depends on database sizing, network, deployment topology, concurrency, data distribution and external services.

Use benchmarks to detect regressions under a controlled runner.

## 49. Compatibility claims should be executable

PyCRMKit qualifies supported Python and optional dependency families through CI.

If your application claims several Python, PostgreSQL or framework versions, encode that matrix in automated tests.

## 50. Keep the main suite broad and fast

The standard PyCRMKit Tests workflow runs pytest with coverage on:

~~~text
Python 3.11
Python 3.12
Python 3.13
~~~

A consuming application should preserve a reasonably fast default developer loop.

## 51. Separate slow resource tests

Use markers, folders or CI jobs to distinguish:

~~~text
fast local tests
live PostgreSQL
migrations
HTTP E2E
security qualification
performance
artifact qualification
~~~

## 52. Suggested application test layout

A consuming repository can use:

~~~text
tests/
├── unit/
│   ├── domain/
│   └── application/
├── integration/
│   ├── persistence/
│   ├── fastapi/
│   └── django/
├── contracts/
├── migrations/
├── security/
├── e2e/
└── qualification/
~~~

The exact folder names are optional. The separation of intent is what matters.

## 53. Unit tests should be deterministic

Avoid network, wall-clock sleeps, shared databases and unordered global state in unit tests.

## 54. Fixtures should reduce boilerplate, not hide the scenario

Useful fixtures include:

~~~text
FixedClock
CRM.memory()
sample Contact
sample Organization
temporary engine
TestClient
~~~

Important business actions should remain visible in the test body.

## 55. Prefer small domain factories

Helpers such as make_contact or make_task can keep setup readable while preserving explicit behavior.

Keep defaults predictable.

## 56. Do not share mutable CRM state across tests

Each test should normally get its own MemoryStore or isolated database state.

Shared global state creates order-dependent failures.

## 57. Test rollback explicitly

Cross-aggregate workflows should have at least one failure-path test.

Examples:

~~~text
merge conflict -> no partial reassignment
commit failure -> no event publication
invalid transition -> no mutation
~~~

## 58. Test post-commit behavior separately

For event-driven behavior distinguish:

~~~text
before commit
after commit
subscriber failure
~~~

The source transaction can remain committed even when a post-commit subscriber raises.

## 59. Test idempotency where retries are plausible

Examples include:

~~~text
lead conversion
webhook delivery
External Identity attach
documented idempotent lifecycle operations
~~~

Invoke the operation twice and assert the stable semantic result.

## 60. Test normalization boundaries

Examples include:

~~~text
email normalization
phone normalization
RelationshipType normalization
Tag name normalization
External Identity system normalization
~~~

Normalization bugs often become uniqueness bugs in production.
