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
