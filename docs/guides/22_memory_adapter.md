# Memory Adapter

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter begins **LEVEL 6 - Persistence & Integrations**.

LEVEL 5 ended at the application data boundary. LEVEL 6 now moves underneath
the domain and application APIs to study how persistence contracts are
implemented.

The official Memory adapter follows this model:

~~~text
MemoryStore
   |
   | committed state
   v
MemoryUnitOfWork.__enter__()
   |
   v
deep-cloned working state
   |
   +--> contacts
   +--> organizations
   +--> relationships
   +--> activities
   +--> tasks
   +--> timeline
   +--> leads
   +--> opportunities
   +--> pipelines
   +--> tags
   +--> custom fields
   +--> external identities
   +--> communication
   +--> audit
   +--> webhooks
   |
   v
explicit commit?
   |
   +--> yes -> publish working state
   |           then dispatch staged events
   |
   +--> no  -> discard working state
~~~

The critical design principle is:

> The Memory adapter is a conformant persistence adapter with explicit
> transaction semantics. It is not a permissive dictionary mock.

## What you will build

You will learn to:

- understand MemoryStore and MemoryUnitOfWork;
- understand committed state versus working state;
- understand explicit commit and rollback;
- understand multi-repository atomicity;
- understand repository copy isolation;
- understand deterministic queries and pagination;
- understand NotFound and lifecycle semantics;
- understand staged Domain Events and post-commit dispatch;
- understand Audit participation in the same transaction;
- understand why nested Memory transactions are rejected;
- understand CRM.memory();
- understand the adapter limits compared with SQL persistence.

## 1. The Memory adapter is official

The package is:

~~~python
pycrmkit.storage.memory
~~~

It is the supported in-process persistence implementation used by tests,
examples, tutorials and local workflows.

## 2. Public components

Stable V1 publicly exports MemoryStore, MemoryUnitOfWork and concrete Memory
repositories for Activities, Audit, Communication, Contacts, Custom Fields,
External Identities, Leads, Opportunities, Organizations, Pipelines,
Relationships, Tags, Tasks, Timeline, Webhook subscriptions and Webhook
deliveries.

These classes are adapter implementations, not domain entities.

## 3. MemoryStore owns committed state

MemoryStore owns one internal committed state containing all supported repository
families.

A newly constructed store is empty and exists only in the current Python
process.

## 4. MemoryStore is the sharing boundary

Sequential Unit of Work instances can share one MemoryStore:

~~~python
store = MemoryStore()

with MemoryUnitOfWork(store) as uow:
    ...
    uow.commit()

with MemoryUnitOfWork(store) as uow:
    ...
~~~

The second transaction sees state committed by the first.

## 5. Entering a transaction clones committed state

MemoryStore begins a transaction by deep-copying its complete committed state.

~~~text
committed state
      |
      | deepcopy
      v
working state
~~~

All repositories in that Unit of Work bind to the same working copy.

## 6. Writes are staged

Inside a Unit of Work, repository writes mutate only the working state.

They do not become committed merely because save was called.

## 7. Commit is explicit

~~~python
with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
    uow.commit()
~~~

Only commit publishes the transaction state to MemoryStore.

## 8. Exit without commit rolls back

~~~python
with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
~~~

The Contact is not persisted because the context exits without an explicit
commit.

## 9. Exceptions roll back

If an exception escapes before commit, staged state is discarded.

Committed store state remains unchanged by that transaction.

## 10. Explicit rollback is supported

Calling rollback inside an active Unit of Work discards staged changes and
rebinds repositories to a fresh snapshot of current committed state.

## 11. Atomicity spans repositories

One MemoryUnitOfWork binds all repositories to the same transaction state.

A Contact update, Organization write and Audit append can therefore be published
by one commit or discarded together.

## 12. Commit clones the working state

MemoryStore publishes a clone of the working state rather than retaining the
same mutable object graph.

That further separates committed state from caller-held transaction objects.

## 13. Transaction isolation and copy isolation differ

Transaction isolation answers:

~~~text
Has staged state been committed?
~~~

Copy isolation answers:

~~~text
Can a caller mutate repository state through a Python object reference?
~~~

The Memory adapter implements both where mutable domain state requires it.

## 14. Save uses copy isolation for mutable aggregates

For Contact and Organization repositories, save stores a deep copy.

Mutating the original object after save does not silently change repository
state.

## 15. Read uses copy isolation for mutable aggregates

get and find return copies for mutable aggregates such as Contact.

Mutating a loaded Contact without saving it again does not persist.

## 16. Why this matters

A naive dictionary fake often stores and returns the exact same Python object.

That makes hidden mutation persistence possible and teaches application code
behavior that a database-backed repository would not provide.

The official Memory adapter avoids that trap.

## 17. Immutable projections can use immutable semantics

TimelineEntry is immutable, so its repository does not need to imitate mutable
aggregate copying mechanically.

The goal is contract fidelity, not copying for its own sake.

## 18. get and find differ

Repository contracts commonly use:

~~~text
get(id)
-> entity or NotFoundError

find(id)
-> entity or None
~~~

Memory repositories preserve that distinction.

## 19. Contact missing semantics

MemoryContactRepository.get raises NotFoundError with code:

~~~text
contact.not_found
~~~

while find returns None for a missing Contact.

## 20. save replaces persisted domain state

Saving the same entity ID again replaces the currently stored aggregate state.

This is how explicit domain changes are persisted.

## 21. Archive remains a lifecycle operation

MemoryContactRepository archive loads the Contact, applies the Contact archive
transition, saves the new state and returns the archived Contact.

It does not hard-delete the record.

## 22. Archived Contacts are hidden by default

ContactQuery excludes archived Contacts unless include_archived is explicitly
enabled.

The Memory repository follows that contract.

## 23. Search is deterministic

MemoryContactRepository sorts results by:

~~~text
created_at ASC
id ASC
~~~

before applying pagination.

## 24. Pagination is exact

Search returns Page values carrying items, limit, offset and total.

The total is computed from the filtered result set before slicing the requested
page.

## 25. Dict insertion order is not repository ordering

The Memory repository explicitly sorts where its contract requires ordering.

Application code should not depend on internal dictionary insertion order.

## 26. Repositories remain domain-specific

Contact search implements ContactQuery rules.

Organization search implements OrganizationQuery rules.

Timeline implements timeline filters and immutable projection behavior.

The adapter is not one generic dictionary CRUD abstraction.

## 27. Timeline append is idempotent for identical content

Appending the same TimelineEntry ID with the same content is accepted.

A conflicting projection under the same ID raises DuplicateError with:

~~~text
timeline.projection.conflict
~~~

## 28. Domain-specific composite keys are preserved

The Memory state uses structures that reflect domain identity, including
definition plus EntityReference for Custom Field values, TagId plus
EntityReference for tag assignments, and system plus external_id for external
identities.

This lets in-memory qualification exercise logical uniqueness boundaries.

## 29. One Unit of Work exposes all repositories

Inside one active MemoryUnitOfWork, Contacts, Organizations, Relationships,
Activities, Tasks, Timeline, Leads, Opportunities, Pipelines, Tags, Custom
Fields, External Identities, Communications, Audit and Webhook repositories all
operate on the same working state.

## 30. Repository access requires an active context

Accessing uow.contacts or calling commit before entering the Unit of Work raises
InvalidStateError with:

~~~text
memory.uow.not_active
~~~

## 31. Re-entering the same Unit of Work is rejected

An already active MemoryUnitOfWork cannot be entered again.

The error code is:

~~~text
memory.uow.already_active
~~~

## 32. One MemoryStore permits one active transaction

MemoryStore also rejects another active MemoryUnitOfWork over the same store.

Nested or concurrent transactions on one MemoryStore are therefore unsupported.

## 33. Nested transactions are intentionally not faked

This pattern is rejected:

~~~python
with MemoryUnitOfWork(store):
    with MemoryUnitOfWork(store):
        pass
~~~

Stable V1 does not pretend to offer savepoints or nested transaction semantics.

## 34. RLock is not database concurrency

MemoryStore uses an internal RLock around committed-state operations and the
active-transaction gate.

That does not provide MVCC, row locks, isolation levels, deadlock semantics or
distributed concurrency.

## 35. Commit can happen once

A second commit on the same active Unit of Work raises InvalidStateError with:

~~~text
memory.uow.already_committed
~~~

## 36. Events are staged

add_event stores Domain Events in a pending list while the transaction is
active.

pending_events exposes an immutable tuple snapshot for diagnostics and tests.

## 37. Events are not published before commit

A staged event remains undispatched while the transaction is only working state.

Rollback or uncommitted exit clears pending events.

## 38. Commit publishes state before events

The order is:

~~~text
capture pending events
      |
      v
publish working state
      |
      v
mark committed
      |
      v
release MemoryStore transaction
      |
      v
dispatch events
~~~

This is a deliberate post-commit event boundary.

## 39. Subscribers can see committed state

Because the MemoryStore transaction is released before synchronous event
handlers run, a subscriber can open a fresh MemoryUnitOfWork on the same store
and read the new committed data.

## 40. Subscriber failure does not undo commit

If a post-commit subscriber raises, the exception propagates but the already
committed MemoryStore state remains committed.

Event dispatch is not part of rollbackable domain state at that point.

## 41. Default event publisher is in-process

Without an explicit publisher, MemoryUnitOfWork uses InProcessEventBus.

CRM.memory normally wires one shared bus to all Unit of Work instances.

## 42. Memory events are not a durable outbox

The adapter does not provide durable queue persistence, broker delivery,
cross-process retries or exactly-once transport.

Its event dispatch is synchronous and in-process.

## 43. Audit behaves differently from post-commit events

AuditEntry is repository state.

Appending an AuditEntry through uow.audit participates in the same working
snapshot as Contact or other domain mutations.

## 44. Audit can commit atomically with domain state

~~~text
save Contact
append AuditEntry
commit
~~~

publishes both in the same MemoryStore transaction.

## 45. Audit rolls back with uncommitted state

If the transaction exits without commit, both the domain mutation and AuditEntry
are discarded.

That is intentionally different from post-commit Domain Event dispatch.

## 46. MemoryUnitOfWork can own its own store

Constructing MemoryUnitOfWork without a store creates a new isolated MemoryStore.

That is convenient for one-off tests but does not share state with separately
constructed Unit of Work instances.

## 47. CRM.memory wires the adapter

CRM.memory creates:

~~~text
one MemoryStore
one shared InProcessEventBus
one UnitOfWork factory
~~~

Each facade operation obtains a new MemoryUnitOfWork over that same store and
bus.

## 48. Each CRM.memory call is isolated

Two independent CRM.memory calls create different MemoryStore instances.

Their CRM state is not shared.

## 49. with_context keeps the same store

CRM.with_context creates a new facade view with different execution context but
the same runtime Unit of Work factory and event bus.

Changing actor or correlation context does not reset Memory persistence.

## 50. with_event also keeps persistence

CRM.with_event changes causal context while preserving the same underlying
Memory persistence and event system.

## 51. Direct repository usage is supported

A MemoryContactRepository can be instantiated directly for focused repository
tests or examples.

Direct repositories are useful for contract qualification.

## 52. Direct repositories do not create cross-repository transactions

Independent repository instances do not automatically share transaction state.

For atomic workflows across repositories, use MemoryStore and MemoryUnitOfWork.

## 53. Repository contracts are reusable

PyCRMKit runs reusable behavioral contract suites against Memory implementations.

For ContactRepository, those contracts cover save/get, optional find, state
replacement, deterministic pagination, normalized search and archive visibility.

## 54. Memory adds adapter-specific copy tests

The Memory Contact repository is additionally tested to prove that mutating an
object after save or after read does not alter persisted state implicitly.

## 55. Unit of Work qualification is behavioral

Tests verify active-context requirements, multi-repository commit,
uncommitted rollback, explicit rollback, exception rollback, copy isolation and
nested-transaction rejection.

## 56. Event and Audit qualification is behavioral

Tests verify Audit atomicity, pending-event staging, post-commit dispatch,
rollback event discard, subscriber visibility of committed state and subscriber
failure after commit.

## 57. Memory is excellent for deterministic application tests

A fresh MemoryStore gives cheap isolated state without an external service while
preserving important repository and Unit of Work semantics.

## 58. Memory does not qualify SQL persistence

Passing Memory tests does not prove ORM mappings, SQL constraints, PostgreSQL
transactions, migrations, connection management or production concurrency.

Those require separate adapters and integration tests.

## 59. Memory cannot model uniqueness races

Because one MemoryStore allows only one active transaction, it does not reproduce
two concurrent database transactions racing over the same unique key.

Database constraints remain necessary.

## 60. Memory has no process durability

The complete store disappears when the Python process ends.

It is not durable storage.

## 61. Memory does not coordinate processes

Two Python processes cannot share the same in-process MemoryStore.

External persistence is required for multi-process applications.

## 62. Memory has no migrations

Its internal Python state evolves with the installed package.

There is no schema migration lifecycle for MemoryStore.

## 63. Memory has no ORM identity-map contract

Application code should reason in terms of domain equality and repository
behavior, not rely on the same Python object instance being returned repeatedly.

## 64. Minimal direct repository example

~~~python
repository = MemoryContactRepository()

repository.save(contact)

loaded = repository.get(contact.id)

assert loaded == contact
assert loaded is not contact
~~~

For mutable Contacts, persistence is state based rather than object-reference
aliasing.

## 65. Minimal Unit of Work commit example

~~~python
store = MemoryStore()

with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
    uow.organizations.save(organization)
    uow.commit()

with MemoryUnitOfWork(store) as uow:
    assert uow.contacts.get(contact.id) == contact
    assert uow.organizations.get(organization.id) == organization
~~~

## 66. Minimal rollback example

~~~python
store = MemoryStore()

with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)

with MemoryUnitOfWork(store) as uow:
    assert uow.contacts.find(contact.id) is None
~~~

No commit means no persisted Contact.

## 67. Explicit rollback example

~~~python
with MemoryUnitOfWork(store) as uow:
    uow.contacts.save(contact)
    uow.rollback()

    assert uow.contacts.find(contact.id) is None
~~~

The working state has been reset to committed state.

## 68. Event staging example

~~~python
with MemoryUnitOfWork(
    store,
    event_publisher=bus,
) as uow:
    uow.contacts.save(contact)
    uow.add_event(event)

    assert uow.pending_events == (event,)
    assert published == []

    uow.commit()

assert published == [event]
~~~

## 69. Cross-repository mental model

~~~text
BEGIN
  |
  v
clone committed state
  |
  v
repositories operate on clone
  |
  +--> domain state
  +--> Audit state
  +--> pending Domain Events
  |
  v
COMMIT?
  |
  +--> no  -> discard working state and events
  |
  +--> yes -> publish state
              release transaction
              dispatch events
~~~

## 70. Why Memory is more than a mock

The adapter preserves application-visible properties that matter across
backends:

~~~text
repository contracts
explicit persistence
NotFound semantics
query filters
deterministic ordering
pagination
lifecycle rules
transaction grouping
commit
rollback
copy isolation
atomic Audit
post-commit events
~~~

It does not pretend to provide infrastructure properties it cannot truthfully
model.

## Common mistakes

### Treating repositories as mutable dictionaries

They implement domain-specific repository contracts and isolation semantics.

### Forgetting commit

Leaving a MemoryUnitOfWork without commit discards staged state.

### Expecting context exit to auto-commit

The stable contract requires explicit commit.

### Mutating a loaded Contact without save

Copy isolation means the mutation is not persisted.

### Assuming get returns None

Use find for optional lookup. get raises NotFoundError.

### Depending on insertion order

Repository ordering is explicit and domain-specific.

### Expecting archived Contacts in default search

They are hidden unless explicitly included.

### Opening nested transactions on one store

The adapter rejects them.

### Interpreting RLock as production concurrency support

Memory does not model database isolation or locking.

### Expecting Domain Events before commit

They are staged and dispatched only after committed state is published.

### Assuming subscriber failure rolls back state

Subscriber work runs after commit.

### Treating Audit and Domain Events as identical

Audit is transactional repository state; Domain Events are post-commit
dispatch.

### Using separate stores and expecting shared state

MemoryStore is the persistence sharing boundary.

### Treating Memory success as PostgreSQL qualification

Database behavior needs database tests.

## Testing the Memory Adapter

Repository tests should cover:

~~~text
save/get/find
missing behavior
replace-on-save
query filters
lifecycle behavior
deterministic ordering
pagination
domain uniqueness and idempotency
~~~

Memory-specific tests should cover:

~~~text
copy on save
copy on read
no hidden mutation persistence
~~~

Unit of Work tests should cover:

~~~text
inactive access rejected
multi-repository commit
exit-without-commit rollback
explicit rollback
exception rollback
nested transaction rejection
second commit rejection
~~~

Event and Audit tests should cover:

~~~text
Audit atomicity
Audit rollback
event staging
no pre-commit dispatch
rollback event discard
post-commit dispatch
subscriber reads committed state
subscriber failure does not undo commit
~~~

## What you learned

You can now explain and use:

- MemoryStore;
- MemoryUnitOfWork;
- the stable Memory repository implementations;
- committed versus working state;
- deep-copy transaction snapshots;
- explicit commit;
- rollback semantics;
- cross-repository atomicity;
- repository copy isolation;
- get versus find;
- deterministic queries and pagination;
- lifecycle/archive behavior;
- Domain Event staging;
- post-commit dispatch;
- Audit atomicity;
- nested transaction rejection;
- CRM.memory wiring;
- the difference between a conformant adapter and a mock;
- the limits of in-process persistence.

## LEVEL 6 in progress

The Persistence & Integrations path now begins with:

~~~text
22 Memory Adapter
~~~

The architecture is:

~~~text
Domain / Application Services
          |
          v
Repository + UnitOfWork contracts
          |
          v
Memory Adapter
          |
          v
in-process committed state
~~~

## Next

The next chapter is **23 - SQLAlchemy**.

The persistence model will become:

~~~text
Domain / Application Services
          |
          v
Repository + UnitOfWork contracts
          |
          +--> Memory Adapter
          |
          +--> SQLAlchemy Adapter
                    |
                    v
              relational database
~~~

The next learning question is:

> How does PyCRMKit map domain entities and repository contracts onto SQLAlchemy
> without leaking ORM models, sessions or persistence concerns into the domain?
