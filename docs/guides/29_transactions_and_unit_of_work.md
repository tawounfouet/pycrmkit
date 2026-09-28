# Transactions & Unit of Work

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

The previous chapters introduced three transaction-capable persistence paths:

~~~text
MemoryUnitOfWork
SQLAlchemyUnitOfWork
DjangoTransactionBridge
~~~

They are not implemented the same way.

Memory uses deep-copy snapshots.
SQLAlchemy uses one shared Session.
Django uses transaction.atomic and, when needed, savepoints.

Yet PyCRMKit still needs a portable application-level transaction model.

The central architecture is:

~~~text
Application Command
      |
      v
Transaction Boundary
      |
      +--> Repository Reads / Writes
      +--> Audit Writes
      +--> Timeline Projection
      +--> Pending Domain Events
      |
      v
COMMIT
      |
      +--> durable / committed state
      |
      v
post-commit event publication
~~~

The central rule is:

> Application code should depend on transaction semantics, not on the concrete
> mechanism that an adapter uses to implement those semantics.

## What you will learn

You will learn to:

- understand the stable UnitOfWork protocol;
- understand why one transaction groups multiple repositories;
- distinguish transaction contract from adapter implementation;
- understand explicit commit;
- understand uncommitted exit rollback;
- understand exception rollback;
- understand explicit rollback-and-continue;
- understand post-commit Domain Event publication;
- understand subscriber failure after commit;
- understand repository/audit/timeline atomicity;
- compare Memory snapshots, SQLAlchemy Sessions and Django atomic blocks;
- understand where nested transaction behavior differs;
- understand where post-commit repository access differs;
- understand cross-aggregate transaction examples such as Lead conversion;
- understand why read-only facade calls do not need commit;
- understand why DjangoTransactionBridge is not the complete UnitOfWork;
- understand transaction error normalization;
- prepare for Context, Events & Audit.

## 1. Unit of Work is a backend-independent protocol

The stable protocol lives at:

~~~text
pycrmkit.core.unit_of_work.UnitOfWork
~~~

It defines one transactional grouping of repositories plus event staging.

## 2. The protocol exposes repository families, not storage engines

The protocol includes repositories such as:

~~~text
activities
communications
contacts
leads
opportunities
pipelines
organizations
relationships
tasks
timeline
tags
custom_fields
external_identities
audit
webhooks
webhook_deliveries
~~~

The protocol does not expose:

~~~text
SQLAlchemy Session
Django QuerySet
MemoryStore internals
database connection
cursor
transaction.atomic object
~~~

## 3. The protocol exposes transaction actions

The portable transaction surface is:

~~~text
add_event(event)
commit()
rollback()
__enter__()
__exit__()
~~~

## 4. Why group repositories in one Unit of Work?

Because real CRM operations frequently affect more than one repository.

Example:

~~~text
Lead conversion
    |
    +--> Lead becomes converted
    +--> Opportunity is created
    +--> Audit entries are written
    +--> Domain Events are staged
~~~

Those writes should succeed or fail together.

## 5. One repository commit per adapter would break atomic workflows

If each repository independently committed:

~~~text
Lead commit succeeds
Opportunity commit fails
        |
        v
inconsistent CRM state
~~~

The Unit of Work owns the transaction instead.

## 6. Repository adapters do not own final commit

The transaction owner is the Unit of Work or transaction bridge.

Repositories persist through the transaction context supplied to them.

## 7. Facade commands open the transaction boundary

A typical write method is:

~~~text
with uow_factory() as uow:
    service(...)
    record_change(...)
    uow.commit()
~~~

## 8. The facade does not know which backend implements the transaction

CRMRuntime stores:

~~~text
uow_factory: Callable[[], UnitOfWork]
~~~

Application composition chooses the concrete adapter.

## 9. Memory and SQLAlchemy implement the full UnitOfWork shape

The Memory and SQLAlchemy adapters expose all repository families required by
the current protocol.

## 10. DjangoTransactionBridge is intentionally narrower

The Django bridge currently exposes:

~~~text
contacts
organizations
relationships
external_identities
~~~

It is therefore a transaction bridge for the implemented Django repository
scope, not the complete cross-domain UnitOfWork protocol.

## 11. This distinction is deliberate

PyCRMKit does not claim structural conformance before an adapter actually
implements the required repository families.

## 12. Explicit commit is the main portable write rule

A successful write transaction must call:

~~~text
commit()
~~~

before leaving the context.

## 13. Exit without commit means rollback

Across the three qualified transaction paths:

~~~text
write
leave context without commit
        |
        v
discard transaction
~~~

## 14. This prevents accidental persistence

A missing commit is safer than implicit persistence.

The application must express transaction intent explicitly.

## 15. Exceptions roll back uncommitted work

If an exception escapes the transaction context before commit:

~~~text
repository writes
      |
      v
exception
      |
      v
rollback
~~~

## 16. Transaction exceptions are not swallowed

The context managers do not suppress the original application exception.

## 17. Multiple repositories commit atomically

Qualified examples include:

~~~text
Contact + Organization
Contact + Organization + Audit
Lead + Opportunity + Pipeline interaction
Contact merge-like coordination + Tags
~~~

## 18. Audit can participate in the same transaction

When audit is enabled and the adapter supports AuditRepository:

~~~text
domain state
   +
audit entry
   |
   v
same Unit of Work
~~~

## 19. Timeline projection can participate in the same transaction

CRMRuntime.record_change may project a supported Domain Event into Timeline
through repositories in the current Unit of Work.

## 20. Event publication does not happen before commit

The portable event rule is:

~~~text
add_event(event)
      |
      v
pending
      |
      v
database/state commit succeeds
      |
      v
publish
~~~

## 21. Pending events are transaction-local

Memory, SQLAlchemy and Django transaction implementations maintain an internal
pending event collection.

## 22. Rollback clears pending events

If the transaction is rolled back:

~~~text
state changes discarded
pending events discarded
~~~

No event should describe state that never committed.

## 23. Uncommitted context exit also clears pending events

Staging an event alone does not make it observable.

Commit is required.

## 24. Subscriber failure happens after commit

The stable rule is:

~~~text
COMMIT succeeds
      |
      v
subscriber runs
      |
      v
subscriber raises
~~~

The exception may reach the caller, but committed state remains committed.

## 25. Post-commit failure is not transaction rollback

~~~text
transaction failure
    !=
post-commit side-effect failure
~~~

## 26. These UoWs do not provide a durable outbox

The default event publisher is an in-process event bus.

The UoW guarantees post-commit ordering, not durable retry/outbox delivery.

## 27. A durable outbox would be a separate reliability mechanism

Crash-safe external delivery requires a durable persistence/retry design beyond
synchronous in-process publication.

## 28. Read-only facade calls do not commit

Examples include:

~~~text
crm.contacts.get(...)
crm.contacts.search(...)
crm.audit.by_correlation(...)
~~~

They open a Unit of Work for repository access but do not intend writes.

## 29. Read-only context exit still closes the transaction boundary

SQLAlchemy closes its Session.

Memory releases its MemoryStore transaction.

## 30. Portable transaction semantics are narrower than implementation details

The common model is:

~~~text
enter
read/write
optional rollback
explicit commit for writes
exit
~~~

# Memory Unit of Work

## 31. Memory uses snapshot isolation by copying state

MemoryStore contains committed in-process state.

Entering MemoryUnitOfWork creates a deep copy of committed state as the working
transaction state.

## 32. Repositories are bound to the working snapshot

Every Memory repository in the transaction operates on the same cloned
_MemoryState.

## 33. Commit replaces committed store state

~~~text
working state
      |
      v
deep copy
      |
      v
MemoryStore committed state
~~~

## 34. Memory commit provides copy isolation

The store does not simply retain references to mutable transaction objects.

## 35. Loaded Memory entities also preserve isolation

Mutating a loaded entity without saving it does not persist the mutation.

## 36. Memory rollback refreshes the working snapshot

rollback discards staged state and replaces it with a fresh snapshot of current
committed store state.

## 37. Memory rollback keeps the UoW active

Repository access remains available inside the entered context.

## 38. Memory supports rollback-and-continue

~~~text
save A
rollback
save B
commit
~~~

## 39. MemoryStore allows one active transaction at a time

The same MemoryStore rejects nested or concurrent MemoryUnitOfWork contexts.

## 40. Nested Memory transactions are unsupported

The error code is:

~~~text
memory.uow.already_active
~~~

## 41. Memory does not implement savepoints

Its transaction model is one active cloned state per MemoryStore.

## 42. Memory releases the store transaction before subscribers

A successful commit calls store._end before synchronous post-commit
subscribers are invoked.

## 43. Subscribers can open a fresh Memory UoW

A subscriber can read the newly committed state in a follow-up transaction.

## 44. Memory event subscribers observe committed state

This behavior is explicitly qualified.

## 45. Memory second commit is rejected

~~~text
uow.commit()
uow.commit()
~~~

The second call raises:

~~~text
memory.uow.already_committed
~~~

## 46. Post-commit repository access is not a portable contract

Portable application code should treat successful commit as the logical end of
the write transaction.

# SQLAlchemy Unit of Work

## 47. SQLAlchemy uses one Session per Unit of Work

Entering SQLAlchemyUnitOfWork creates one Session from the configured factory.

## 48. Every SQLAlchemy repository shares that Session

The adapter binds all current repository instances to the same Session.

## 49. Shared Session means shared database transaction

Writes across repositories participate in one database transaction.

## 50. Repositories do not independently commit

SQLAlchemyUnitOfWork owns Session.commit.

## 51. SQLAlchemy commit order

~~~text
stage repository writes
      |
      v
Session.commit()
      |
      v
mark committed
      |
      v
clear pending events
      |
      v
publish events
~~~

## 52. SQLAlchemy commit failure rolls back

If Session.commit raises SQLAlchemyError:

~~~text
Session.rollback()
pending events cleared
error translated
~~~

## 53. SQLAlchemy errors cross a backend-neutral boundary

translate_sqlalchemy_error maps backend failures into PyCRMKit repository
errors.

## 54. Failed commit does not publish events

No post-commit event is emitted for a database transaction that failed.

## 55. Unexpected commit exceptions also roll back

The implementation rolls back and clears events before re-raising.

## 56. SQLAlchemy rollback keeps the UoW usable

Session.rollback discards uncommitted changes without closing the Session.

## 57. SQLAlchemy rollback-and-continue is qualified

~~~text
save Contact
rollback
Contact absent
save Organization
commit
Organization persisted
~~~

## 58. SQLAlchemy uncommitted exit rolls back

If the context exits with an open uncommitted transaction, Session.rollback is
called.

## 59. SQLAlchemy context exit closes the Session

The Session is closed and repository bindings are released.

## 60. SQLAlchemy second commit is rejected

~~~text
sqlalchemy.uow.already_committed
~~~

## 61. SQLAlchemy repository access requires active context

Before enter:

~~~text
sqlalchemy.uow.not_active
~~~

## 62. Active context and open transaction are distinct state

The implementation tracks both.

## 63. add_event requires an open transaction

A committed SQLAlchemy UoW cannot stage new transactional events.

## 64. rollback requires an open transaction

Rollback after commit is not a valid continuation.

## 65. Post-commit subscribers can open fresh SQLAlchemy UoWs

A subscriber can obtain a new Session and read committed state.

## 66. Subscriber failure leaves database state committed

This is explicitly tested.

## 67. SQLAlchemy is the full relational UnitOfWork implementation

It binds all repository families currently required by UnitOfWork.

# Django Transaction Bridge

## 68. Django uses transaction.atomic

Entering DjangoTransactionBridge opens an atomic block.

## 69. The bridge binds only implemented Django repositories

Current V1 scope:

~~~text
contacts
organizations
relationships
external_identities
~~~

## 70. Top-level commit exits the current atomic block

At top level, leaving the internal atomic block successfully commits the
database transaction.

## 71. Django exit without commit forces rollback

The bridge uses an internal rollback signal to leave the atomic block as a
rollback.

## 72. Django exception exit rolls back

An escaping application exception is passed through the atomic context exit.

## 73. Django rollback reopens a fresh atomic block

~~~text
rollback current atomic
clear pending events
open fresh atomic
keep bridge active
~~~

## 74. Django rollback-and-continue is qualified

~~~text
save A
rollback
save B
commit
~~~

## 75. Django repository access after commit is rejected

~~~text
django.transaction.already_committed
~~~

## 76. Django repository access before enter is rejected

~~~text
django.transaction.not_active
~~~

## 77. Django commit failure is normalized

~~~text
django.transaction.commit_failed
~~~

## 78. Django begin failure is normalized

~~~text
django.transaction.begin_failed
~~~

## 79. Django rollback failure is normalized

~~~text
django.transaction.rollback_failed
~~~

## 80. Django can join an ambient transaction

Before opening its own atomic block, the bridge checks whether the connection
is already inside transaction.atomic.

## 81. Ambient transaction means savepoint behavior

~~~text
outer transaction.atomic
      |
      v
inner bridge atomic
      |
      v
savepoint
~~~

## 82. bridge.commit may not be final durability

Inside an ambient transaction, bridge.commit can release only the inner
savepoint while the outer transaction still controls the real commit.

## 83. This is the largest transaction semantic difference

Memory and SQLAlchemy UoWs normally own their transaction boundary directly.

DjangoTransactionBridge can live inside a larger transaction it does not own.

## 84. Django records whether it joined an ambient transaction

That state controls event publication.

## 85. Top-level Django events publish after commit

If the bridge owns the top-level transaction, events publish after the atomic
block commits.

## 86. Ambient Django events are deferred

The bridge registers event publication through transaction.on_commit.

## 87. on_commit respects outer transaction ownership

Events wait for the actual outer database commit.

## 88. Outer rollback discards the callback

~~~text
outer rollback
      |
      +--> bridge writes discarded
      +--> on_commit callback discarded
      +--> events unpublished
~~~

## 89. The business invariant remains portable

No Domain Event should be published for state that did not ultimately commit.

## 90. Django subscriber failure after top-level commit cannot undo state

Post-commit publication occurs after successful database commit.

# Portable versus adapter-specific guarantees

## 91. Portable: context entry is required

Transaction implementations reject invalid use before enter.

## 92. Portable: multiple repository writes can be grouped

Related persistence work can share a transaction boundary.

## 93. Portable: write transactions require explicit commit

Normal context exit does not imply write commit.

## 94. Portable: exit without commit discards uncommitted work

This is a stable cross-adapter guarantee.

## 95. Portable: application exceptions discard uncommitted work

A failed command should not leave half-applied state.

## 96. Portable: rollback discards staged state

All three transaction paths implement rollback.

## 97. Portable: rollback can continue inside the entered boundary

This is qualified for Memory, SQLAlchemy and Django.

## 98. Portable: rollback clears pending events

Rolled-back state does not publish committed events.

## 99. Portable: events publish only after effective commit

For ambient Django transactions, effective commit means the outermost commit.

## 100. Portable: subscriber failure does not undo committed state

Post-commit effects are outside rollback.

## 101. Portable: repeated commit is invalid

One transaction is not repeatedly committable.

## 102. Adapter-specific: implementation mechanism

~~~text
Memory      -> deep-copy snapshot
SQLAlchemy  -> shared Session
Django      -> transaction.atomic / savepoint
~~~

## 103. Adapter-specific: nested behavior

~~~text
Memory
  nested same-store transaction -> rejected

SQLAlchemy
  separate UoWs -> separate Sessions

Django
  ambient outer transaction -> joined through savepoint
~~~

## 104. Adapter-specific: post-commit object lifecycle

The implementations do not promise identical repository usability after
commit.

Portable code should stop using the transaction after commit.

## 105. Adapter-specific: transaction error translation

Memory transaction-state errors use memory.uow codes.

SQLAlchemy translates backend/database errors.

Django normalizes begin/commit/rollback failures.

## 106. Adapter-specific: concurrency

Memory's one-active-UoW store is not a database concurrency model.

PostgreSQL supplies real concurrency/constraint behavior through the relational
adapters.

## 107. Adapter-specific: isolation level

UnitOfWork does not define one universal SQL isolation level.

Database configuration owns it.

## 108. Adapter-specific: savepoints

The current Django bridge explicitly supports ambient savepoint participation.

The base UnitOfWork protocol does not expose a savepoint API.

## 109. Good abstraction does not erase correctness-relevant differences

The portable contract hides storage mechanics while documenting behavior that
can affect transaction correctness.

# Facade transaction patterns

## 110. Contact create is one write transaction

~~~text
open UoW
      |
      v
ContactService.create
      |
      v
record_change
      |
      v
commit
~~~

## 111. Contact update follows the same pattern

Domain mutation and its audit/timeline/event work share the transaction.

## 112. Lead conversion is a stronger example

Lead conversion coordinates:

~~~text
LeadRepository
OpportunityRepository
PipelineRepository
AuditRepository
Timeline-capable repositories
pending Domain Events
~~~

through one Unit of Work.

## 113. Idempotent Lead conversion may return without new commit

If conversion reports an existing Opportunity and creates no new state, the
facade can return it without committing new writes.

## 114. Cross-repository composition is why UnitOfWork exists

Without one shared transaction, Lead and Opportunity state could diverge.

## 115. Opportunity stage transitions coordinate state and audit

The SQLAlchemy E2E verifies stage changes and audit records through the same
transaction infrastructure.

## 116. Contact merge coordinates related repositories

Merge can reconcile Contact state and linked references inside one transaction
boundary.

## 117. Bulk operations need the same discipline

A loop of repository saves remains one transaction until commit.

## 118. Loop completion is not commit

Durability begins only after commit succeeds.

## 119. Failure before commit should leave no staged batch durable

That is the transaction foundation.

# Events, Audit and Timeline

## 120. record_change can coordinate three concerns

CRMRuntime.record_change may:

~~~text
project Timeline
append Audit
stage Domain Event
~~~

inside the current transaction.

## 121. Timeline projection occurs before commit

Projection writes through repositories in the current UoW.

## 122. Audit persistence occurs before commit

AuditService appends through uow.audit in the same transaction.

## 123. Domain Event publication occurs after commit

The event is staged through uow.add_event instead of being published
immediately.

## 124. The ordering is intentional

~~~text
domain state write
      +
timeline/audit write
      |
      v
COMMIT
      |
      v
Domain Event subscribers
~~~

## 125. Context metadata travels with events

The next chapter focuses on actor_id, correlation_id and causation_id.

Transaction semantics ensure those events are not published for rolled-back
state.

# Designing application code

## 126. Prefer facade commands for ordinary application work

The CRM facade already owns transaction boundaries for supported commands.

## 127. Use UnitOfWork directly for custom atomic workflows

Custom application services may coordinate repositories explicitly when no
public facade command exists.

## 128. Keep commit ownership clear

One layer should clearly own transaction commit.

## 129. Do not commit inside repository implementations

That breaks cross-repository atomic composition.

## 130. Do not publish transactional events before commit

Listeners could observe state that later rolls back.

## 131. Commit does not guarantee post-commit side effects succeeded

Persistence may be committed even if a synchronous subscriber fails afterward.

## 132. Decide whether post-commit effects require durable retry

If they do, introduce an explicit durable delivery mechanism.

## 133. Do not infer PostgreSQL concurrency from Memory

Memory is a deterministic reference adapter, not a database race simulator.

## 134. Do not infer savepoints from UnitOfWork

The protocol defines rollback, not nested savepoint controls.

## 135. Do not keep using a transaction after commit

Portable lifecycle ends logically at commit.

## 136. Open a fresh UnitOfWork for follow-up work

The next command or subscriber should use a new transaction boundary.

## Common mistakes

### Letting repositories commit themselves

This destroys cross-repository atomicity.

### Assuming context exit commits automatically

PyCRMKit write transactions require explicit commit.

### Publishing events before commit

Rolled-back state must not generate committed events.

### Assuming subscriber failure rolls back the database

The transaction has already committed.

### Treating Memory nested transactions like Django savepoints

Memory rejects nested transactions on the same store.

### Treating Django bridge commit inside outer atomic as final durability

The outer transaction still owns the real commit.

### Treating DjangoTransactionBridge as the complete UnitOfWork

Its repository scope is intentionally bounded.

### Assuming all adapters expose identical behavior after commit

Portable code should stop using the transaction after commit.

### Using Memory to test PostgreSQL race conditions

Database concurrency belongs to PostgreSQL qualification.

### Forgetting rollback also discards pending events

That is required for consistency.

### Treating in-process post-commit publication as a durable outbox

It is not.

## Testing transaction semantics

Portable transaction tests should cover:

~~~text
repository access requires entered context
multi-repository commit
exit without commit rollback
exception rollback
explicit rollback
rollback-and-continue
pending event staging
rollback clears events
commit publishes events
subscriber failure leaves committed state
second commit rejected
~~~

Memory-specific tests should cover:

~~~text
snapshot copy isolation
mutation without save does not persist
nested same-store UoW rejected
subscriber can open fresh UoW after commit
~~~

SQLAlchemy-specific tests should cover:

~~~text
all repositories share one Session
Session commit / rollback
commit failure translation
Session close on exit
database-backed multi-repository atomicity
fresh UoW after commit
~~~

Django-specific tests should cover:

~~~text
transaction.atomic ownership
explicit rollback + reopen
ambient outer transaction
savepoint commit
on_commit event deferral
outer rollback discards event callback
begin / commit / rollback error normalization
post-commit access rejection
~~~

Cross-domain E2E should cover:

~~~text
Lead conversion
Pipeline transition
Audit in same transaction
Contact merge-like coordination
bulk writes
~~~

## What you learned

You can now explain:

- the UnitOfWork protocol;
- why multiple repositories share one transaction;
- why explicit commit is required;
- why uncommitted exit rolls back;
- why exceptions roll back;
- rollback-and-continue semantics;
- post-commit Domain Event publication;
- why subscriber failure cannot undo committed state;
- Memory snapshot transactions;
- SQLAlchemy shared-Session transactions;
- Django atomic/savepoint transactions;
- portable versus adapter-specific semantics;
- why DjangoTransactionBridge is intentionally bounded;
- why transaction ownership matters in facade and custom workflows.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter              ✅
23 SQLAlchemy                  ✅
24 PostgreSQL                  ✅
25 Migrations                  ✅
26 FastAPI                     ✅
27 Django                      ✅
28 Django REST Framework       ✅
29 Transactions & Unit of Work ✅
30 Context, Events & Audit     ← NEXT
31 Error Handling
32 Security & Privacy
~~~

The transaction abstraction can be summarized as:

~~~text
Memory
   snapshot
      \
       \
SQLAlchemy ----> portable transaction semantics
   Session      /
              /
Django
 atomic/savepoint
~~~

## Next

The next chapter is **30 - Context, Events & Audit**.

The next architecture is:

~~~text
Request / Application Context
      |
      +--> actor_id
      +--> correlation_id
      +--> causation_id
      |
      v
CRM command
      |
      v
Domain Event
      |
      +--> Timeline projection
      +--> Audit entry
      |
      v
Unit of Work commit
      |
      v
post-commit event subscribers
~~~

The next learning question is:

> How does PyCRMKit carry actor, correlation and causation context through domain
> changes, transactional audit records, Timeline projection and post-commit
> Domain Events without coupling the domain to HTTP or a specific framework?
