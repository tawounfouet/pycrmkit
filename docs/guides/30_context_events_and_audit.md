# Context, Events & Audit

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 29 established the transaction boundary:

~~~text
application command
      |
      v
Unit of Work
      |
      +--> domain state
      +--> audit
      +--> timeline
      +--> pending events
      |
      v
COMMIT
      |
      v
post-commit subscribers
~~~

This chapter focuses on the metadata that explains **who caused the change,
which operation trace it belongs to, which event directly caused it, how that
context reaches Domain Events, what Audit stores, and what Timeline projects**.

The central architecture is:

~~~text
Request / Application Context
      |
      +--> actor_id
      +--> correlation_id
      +--> causation_id
      |
      v
CRM facade command
      |
      v
CRMRuntime.record_change
      |
      +--> DomainEvent
      +--> Timeline projection when supported
      +--> AuditEntry when enabled
      +--> staged event when enabled
      |
      v
Unit of Work commit
      |
      v
InProcessEventBus
      |
      v
subscribers / webhook bridge
~~~

The central rule is:

> Context is attached at the application/facade boundary and copied into
> immutable event/audit/timeline records. The domain does not depend on HTTP,
> FastAPI, DRF, Django or a tracing vendor.

## What you will learn

You will learn to:

- understand CRMConfig and CRMContext;
- distinguish actor, correlation and causation;
- understand default context from configuration;
- understand immutable contextual CRM views;
- use CRM.with_context;
- use CRMContext.from_event and CRM.with_event;
- understand correlation fallback when a parent event has no trace ID;
- understand the DomainEvent envelope;
- understand EventId, EventType and schema_version;
- understand event registry and serializer governance;
- understand synchronous in-process subscribers;
- understand exact-type subscription behavior;
- understand transactional event staging;
- understand post-commit publication;
- understand AuditEntry and AuditService;
- understand audit PII minimization;
- understand which context fields Audit persists;
- understand Timeline projection and supported event types;
- understand which context fields Timeline persists;
- understand timeline replay identity;
- understand independent event/audit/timeline switches;
- understand FastAPI and DRF request-context bridges;
- understand multi-hop causation chains;
- understand automatic event-to-webhook bridging;
- prepare for Error Handling.

# Context

## 1. CRMContext is the operation-context value object

The stable public context is:

~~~text
CRMContext
├── actor_id
├── correlation_id
└── causation_id
~~~

It lives in:

~~~text
pycrmkit.config.CRMContext
~~~

## 2. Context is immutable

CRMContext is a frozen dataclass.

A running operation does not mutate the context object in place.

## 3. actor_id answers who initiated the operation

Typical values include:

~~~text
user-42
agent-7
system
import-worker
api-client-123
~~~

It is optional.

## 4. actor_id is normalized

If present, actor_id is trimmed.

A blank value is rejected.

Stable error:

~~~text
ValidationError
code = crm.actor_id.invalid
~~~

## 5. correlation_id identifies the broader trace

correlation_id answers:

> Which request, workflow, business operation or trace does this mutation belong
> to?

Examples:

~~~text
request-900
bulk-import-2026-09-28
checkout-123
workflow-abc
~~~

## 6. correlation_id is optional

A root application operation can omit it.

PyCRMKit does not silently invent a correlation ID for every direct command.

## 7. Blank correlation IDs are rejected

Stable error:

~~~text
ValidationError
code = crm.correlation_id.invalid
~~~

## 8. causation_id points to the direct parent event

causation_id is:

~~~text
None
or
EventId
~~~

It answers:

> Which DomainEvent directly caused this new operation?

## 9. causation_id is strongly typed

Passing an arbitrary string instead of EventId is rejected.

Stable error:

~~~text
ValidationError
code = crm.causation_id.invalid
~~~

## 10. Correlation and causation solve different problems

~~~text
correlation_id
= trace / business-flow identity

causation_id
= direct event parent
~~~

A chain may share one correlation while each event has a different direct
causation parent.

## 11. CRMConfig can seed default context

CRMConfig contains:

~~~text
events_enabled
audit_enabled
default_actor_id
default_correlation_id
~~~

## 12. Default configuration enables events and audit

The stable defaults are:

~~~text
events_enabled = True
audit_enabled  = True
~~~

## 13. Default actor/correlation are optional

By default:

~~~text
default_actor_id       = None
default_correlation_id = None
~~~

## 14. CRM initialization uses configuration defaults

When CRM is created without an explicit CRMContext:

~~~text
CRMConfig defaults
      |
      v
initial CRMContext
~~~

## 15. Explicit CRMContext overrides config defaults

If the application passes a context explicitly, that context becomes the
runtime context.

## 16. CRM.context exposes the current immutable context

Applications can inspect:

~~~text
crm.context.actor_id
crm.context.correlation_id
crm.context.causation_id
~~~

## 17. with_context creates a facade view

Example:

~~~python
scoped = crm.with_context(
    actor_id="agent-7",
    correlation_id="request-900",
)
~~~

The returned object is another CRM facade view.

## 18. with_context does not create a new backend

The new facade shares the same underlying:

~~~text
uow_factory
event bus
ID factory
clock
integration objects
webhook bridge
~~~

## 19. Context views therefore see the same persisted state

A Contact created through a scoped facade is readable through the original CRM.

## 20. with_context supports partial overrides

If only actor_id is supplied:

~~~text
actor_id       = new actor
correlation_id = current correlation
causation_id   = current causation
~~~

The same preservation rule applies to other omitted context fields.

## 21. Passing None is different from omitting a field

with_context uses an internal sentinel.

Therefore:

~~~text
field omitted -> preserve current value
field=None    -> explicitly clear value
~~~

## 22. This mirrors explicit update semantics elsewhere

The same design principle appears in domain PATCH DTOs:

~~~text
omitted
!=
explicit null
~~~

# Event-derived context

## 23. CRMContext.from_event creates child-operation context

Given a parent DomainEvent:

~~~python
child_context = CRMContext.from_event(parent)
~~~

the stable mapping is:

~~~text
actor_id       = parent.actor_id
correlation_id = parent.correlation_id or str(parent.id)
causation_id   = parent.id
~~~

## 24. Actor identity propagates through event-triggered work

If the parent event was caused by actor agent-7, the child context keeps
agent-7.

## 25. Existing correlation propagates unchanged

If the parent has:

~~~text
correlation_id = request-900
~~~

the child context keeps request-900.

## 26. Missing parent correlation gets a trace root

If parent.correlation_id is None:

~~~text
child correlation_id = str(parent.id)
~~~

The parent EventId becomes the trace root.

## 27. Direct causation always points to the parent event

~~~text
child causation_id = parent.id
~~~

## 28. CRM.with_event is the facade convenience

Instead of constructing CRMContext manually:

~~~python
child_crm = crm.with_event(parent_event)
~~~

## 29. with_event shares backend and integrations

Like with_context, it creates a lightweight facade view around the same runtime
dependencies.

## 30. Multi-hop propagation preserves the trace

Consider:

~~~text
contact.created
      |
      v
task.created
      |
      v
task.completed
~~~

If the root carries correlation request-900:

~~~text
contact.created
correlation = request-900
causation   = None

task.created
correlation = request-900
causation   = contact.created.id

task.completed
correlation = request-900
causation   = task.created.id
~~~

## 31. Correlation answers chain membership

All three events belong to the same broader trace.

## 32. Causation answers immediate lineage

Each child points only to its direct parent event.

## 33. The two fields support reconstructable event graphs

Applications can group by correlation and follow direct parent links through
causation.

# DomainEvent

## 34. DomainEvent is the immutable event envelope

The stable public envelope is:

~~~text
id
type
schema_version
aggregate_type
aggregate_id
occurred_at
actor_id
correlation_id
causation_id
payload
metadata
~~~

## 35. DomainEvent is frozen

Events represent facts that occurred.

They are not mutable workflow commands.

## 36. EventId identifies one occurrence

Two contact.created events have different EventId values even if they refer to
the same Contact at different times.

## 37. EventType identifies the semantic event name

Examples:

~~~text
contact.created
task.completed
lead.converted
opportunity.won
email.delivered
~~~

## 38. EventType values are normalized and validated

Public event names use a dotted lowercase identifier contract.

## 39. schema_version is separate from package version

Example:

~~~text
PyCRMKit package = 1.0.0
contact.created schema_version = 1
~~~

## 40. Public event contract identity is type plus schema version

~~~text
(event_type, schema_version)
~~~

## 41. aggregate_type identifies the emitting domain family

Examples:

~~~text
contact
task
lead
opportunity
communication_record
~~~

## 42. aggregate_id identifies the source aggregate

DomainEvent.create converts supplied identifiers to strings.

## 43. occurred_at uses the injected Clock

This keeps event time deterministic in tests and normalizes time semantics.

## 44. actor/correlation/causation are copied from CRMContext

CRMRuntime.record_change passes:

~~~text
runtime.context.actor_id
runtime.context.correlation_id
runtime.context.causation_id
~~~

into DomainEvent.create.

## 45. payload carries event-specific public facts

Examples include:

~~~text
status
pipeline_id
opportunity_id
lead_id
provider
business_occurred_at
~~~

## 46. metadata is distinct from payload

It is another immutable JSON-compatible mapping in the event envelope.

## 47. Payload and metadata are deeply frozen

Mutable JSON containers are normalized into immutable internal forms.

## 48. Events remain JSON-oriented

The envelope is designed for:

~~~text
serialization
webhooks
signing
fixtures
external consumers
in-process subscribers
~~~

# Event governance

## 49. EventRegistry governs public type/version pairs

EventRegistry stores EventDefinition values identified by:

~~~text
event_type
schema_version
~~~

## 50. Registry support is exact

If contact.created v1 is registered, that does not implicitly register v2.

## 51. Multiple schema versions can coexist

The registry can contain:

~~~text
contact.created v1
contact.created v2
~~~

as distinct contracts.

## 52. default_event_registry returns stable built-ins

The current stable registry contains 41 built-in v1 event types.

## 53. Registry state is fresh per call

Applications can extend their own registry without mutating a global singleton.

## 54. Custom DomainEvent creation is possible without registry membership

DomainEvent validates the generic envelope.

It does not require an EventRegistry entry merely to exist in memory.

## 55. Governed serialization requires registry support

EventSerializer validates the exact event type/schema pair before public
serialization.

## 56. EventSerializer provides deterministic JSON

Its stable JSON settings are:

~~~text
ensure_ascii = False
sort_keys    = True
compact separators
~~~

## 57. Deterministic serialization is useful for webhook signing

The same event envelope produces stable canonical bytes for signing and
transport.

# In-process event bus

## 58. InProcessEventBus is synchronous

Handlers execute in the publishing thread/process.

## 59. Subscription is exact by EventType

~~~python
crm.events.subscribe(
    "contact.created",
    handler,
)
~~~

does not subscribe to contact.updated.

## 60. V1 has no wildcard subscription syntax

Subscriptions target exact event types.

## 61. Handlers execute in subscription order

The event bus preserves deterministic handler ordering.

## 62. Duplicate subscription is idempotent

Registering the same handler twice for the same event type does not duplicate
delivery.

## 63. unsubscribe reports whether a handler existed

The public facade exposes unsubscribe through crm.events.

## 64. crm.events also supports decorator registration

~~~python
@crm.events.on("task.completed")
def on_completed(event):
    ...
~~~

## 65. crm.events does not expose arbitrary publish

The public EventsAPI exposes:

~~~text
subscribe
unsubscribe
on
~~~

Business events normally originate from facade mutations.

## 66. Handler failures propagate

The synchronous bus does not swallow subscriber exceptions.

## 67. The bus does not provide durable messaging

It has no built-in:

~~~text
persistent queue
consumer offsets
dead-letter queue
distributed worker
durable retry
~~~

## 68. Durable webhook delivery is a separate layer

Webhook delivery uses persisted delivery state and retries, but the in-process
bus itself remains synchronous and process-local.

# Transactional event staging

## 69. Facade mutations call CRMRuntime.record_change

This is the main cross-cutting bridge for:

~~~text
event creation
timeline projection
audit recording
event staging
~~~

## 70. record_change first checks whether work is needed

If:

~~~text
events disabled
audit disabled
timeline does not support event
~~~

it returns None without creating a DomainEvent.

## 71. Supported Timeline events can still require an internal DomainEvent

Even when event publication and audit are disabled, Timeline projection needs a
DomainEvent envelope for supported lifecycle events.

## 72. Timeline support therefore affects the early-return decision

This is why Timeline is not merely another EventBus subscriber.

## 73. Timeline projection happens before commit

TimelineProjector writes through uow.timeline inside the current transaction.

## 74. Audit recording happens before commit

AuditService writes through uow.audit inside the current transaction.

## 75. EventBus publication is only staged before commit

If events are enabled:

~~~text
uow.add_event(event)
~~~

stores the event for post-commit publication.

## 76. Commit order protects consistency

~~~text
domain writes
      +
timeline projection
      +
audit entry
      +
pending event
      |
      v
COMMIT
      |
      v
event subscribers
~~~

## 77. Rollback removes source state and projections together

Transactional Timeline/Audit writes are discarded if the Unit of Work rolls
back.

## 78. Pending events are also discarded

No post-commit event is published for rolled-back state.

## 79. Subscriber exceptions happen after source commit

A subscriber failure can propagate while source state remains committed.

# Audit

## 80. AuditEntry is an immutable operational mutation record

Its stable fields are:

~~~text
id
actor_id
action
entity_type
entity_id
occurred_at
changes
correlation_id
~~~

## 81. Audit does not currently persist causation_id

The current AuditEntry contract carries:

~~~text
actor_id
correlation_id
~~~

but not:

~~~text
causation_id
~~~

Direct event lineage remains on DomainEvent.

## 82. AuditEntry action uses dotted lowercase identifiers

Examples:

~~~text
contact.created
task.completed
opportunity.stage_changed
~~~

## 83. Audit entity_type is normalized

The value is trimmed and case-folded.

## 84. Audit entries are append-oriented and immutable

The AuditRepository contract provides append, read and query operations rather
than general mutation.

## 85. AuditService uses injected ID and Clock

Audit creation remains deterministic/testable.

## 86. AuditService.record accepts explicit changes

The caller decides what change summary should be persisted.

## 87. Explicit changes enable privacy minimization

AuditService does not introspect an entire entity and dump all fields
automatically.

## 88. record_event copies event context

AuditService.record_event copies:

~~~text
event.type       -> action
aggregate_type   -> entity_type
aggregate_id     -> entity_id
actor_id         -> actor_id
correlation_id   -> correlation_id
~~~

## 89. record_event does not copy event payload by default

This is an explicit privacy boundary.

An event payload can contain public transport facts that should not
automatically become audit change details.

## 90. Facade audit changes often contain field names, not values

For create operations, present_fields records which fields were supplied.

For update operations, revision_fields records which DTO fields changed.

## 91. This reduces accidental PII persistence

A Contact audit change can say:

~~~text
fields = ["first_name", "last_name"]
~~~

without copying the actual name values.

## 92. Audit is queryable by entity

~~~text
crm.audit.for_entity(entity_type, entity_id)
~~~

## 93. Audit is queryable by actor

~~~text
crm.audit.by_actor(actor_id)
~~~

## 94. Audit is queryable by correlation

~~~text
crm.audit.by_correlation(correlation_id)
~~~

## 95. Correlation query reconstructs a mutation trace

All audit records carrying one correlation ID can be retrieved together.

# Timeline

## 96. Timeline is a customer-facing read projection

Timeline is distinct from both Domain Events and Audit.

~~~text
Domain Event
= domain fact

Audit
= operational mutation trace

Timeline
= selected customer-facing historical projection
~~~

## 97. TimelineEntry is immutable

Its stable fields include:

~~~text
id
kind
event_type
source_event_id
entity
occurred_at
title
summary
references
actor_id
correlation_id
metadata
~~~

## 98. Timeline does not currently persist causation_id

Like Audit, Timeline keeps:

~~~text
actor_id
correlation_id
~~~

but not direct causation.

## 99. TimelineEntryId is derived from EventId

The entry ID uses the same UUID value as source_event_id.

## 100. Event identity therefore becomes projection replay identity

Replaying the same source event can be idempotent.

## 101. TimelineProjector supports selected meaningful events

The current supported set is:

~~~text
activity.created

task.created
task.started
task.completed
task.cancelled
task.reopened

email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

## 102. Not every Domain Event becomes customer history

Examples such as:

~~~text
contact.updated
lead.qualified
pipeline.created
tag.created
~~~

are not automatically projected into Timeline.

## 103. This prevents operational noise from becoming customer history

Timeline selects meaningful activity/task/communication occurrences.

## 104. Activity projection uses business occurrence time

For imported or historical Activity records:

~~~text
TimelineEntry.occurred_at = Activity.occurred_at
~~~

not necessarily event creation time.

## 105. Task projections use lifecycle timestamps

task.started uses started_at when available.

task.completed uses completed_at.

Other task lifecycle projections use the appropriate task business timestamp.

## 106. Email projection can use business_occurred_at payload

If present and valid, communication projection can use the event payload's
business occurrence timestamp.

## 107. Timeline propagates actor and correlation

Projection helpers copy those fields from DomainEvent.

## 108. Timeline source event remains traceable

source_event_id links the projection back to the originating event occurrence.

# Independent switches

## 109. Event publication and Audit are independently configurable

These configurations are valid:

~~~text
events=True,  audit=True
events=False, audit=True
events=True,  audit=False
events=False, audit=False
~~~

## 110. events_enabled controls EventBus staging

When false, record_change does not call uow.add_event.

## 111. audit_enabled controls AuditService recording

When false, no AuditEntry is appended by record_change.

## 112. Timeline is not controlled by either flag

For supported Timeline events, projection can still happen even if both flags
are false.

## 113. This is a deliberate architecture boundary

Timeline is a transactional read model, not an external side effect.

## 114. Events and Audit can be disabled without disabling customer history

A Task lifecycle can still project to Timeline if its source operation is
performed through the facade.

# Transport context bridges

## 115. FastAPI understands actor and correlation headers

The stable headers are:

~~~text
X-Actor-ID
X-Correlation-ID
~~~

## 116. FastAPI does not expose a causation header

The current integration propagates actor/correlation only from HTTP.

Applications can use with_event or with_context for causation-aware internal
work.

## 117. DRF uses the same two headers

~~~text
X-Actor-ID
X-Correlation-ID
~~~

## 118. DRF also does not expose causation through a public header contract

Direct causation is an application/event-workflow concern.

## 119. Missing HTTP headers preserve base context

Both transport adapters preserve configured context values when a header is
omitted.

## 120. HTTP frameworks do not leak into CRMContext

CRMContext contains semantic metadata only.

It does not know:

~~~text
Header
Request
FastAPI
DRF
Django
ASGI
WSGI
~~~

# Webhook event bridge

## 121. EventBus can feed the webhook bridge after commit

The stable flow is:

~~~text
CRM mutation
      |
      v
source transaction commit
      |
      v
DomainEvent publication
      |
      v
WebhookEventBridge
      |
      v
matching subscriptions
      |
      v
delivery engine
~~~

## 122. Webhook filtering uses exact event types

Subscriptions choose the event types they receive.

## 123. Webhook serialization uses the governed event contract

Canonical EventSerializer output is used for public webhook payloads/signing.

## 124. Webhook request carries event identity/type headers

The stable transport includes headers such as:

~~~text
X-PyCRMKit-Event-ID
X-PyCRMKit-Event-Type
~~~

## 125. Webhook delivery happens after source commit

This follows the same post-commit side-effect rule as other event subscribers.

## 126. Webhook delivery state has separate persistence/retry semantics

Source transaction success and webhook delivery success are different
transactions/concerns.

# Multi-hop example

## 127. Start a root operation with explicit request context

~~~python
root_crm = crm.with_context(
    actor_id="agent-7",
    correlation_id="request-900",
)
~~~

## 128. Capture the root event

~~~python
events = []
crm.events.subscribe(
    "contact.created",
    events.append,
)

contact = root_crm.contacts.create(
    display_name="Ada Lovelace",
)

root_event = events[0]
~~~

## 129. Start child work with with_event

~~~python
task = crm.with_event(
    root_event,
).tasks.create(
    title="Follow up",
)
~~~

## 130. Child actor/correlation remain stable

~~~text
actor_id       = agent-7
correlation_id = request-900
~~~

## 131. Child causation points to root EventId

~~~text
causation_id = root_event.id
~~~

## 132. A second child can continue the chain

If task.completed is triggered from task.created:

~~~text
task.completed.causation_id
=
task.created.id
~~~

## 133. Audit can group the chain by correlation

~~~python
trace = crm.audit.by_correlation(
    "request-900"
)
~~~

## 134. Timeline can show selected customer-facing parts

If the Task references the Contact, the Task lifecycle events appear in the
Contact Timeline.

## 135. Timeline and Audit tell different stories

~~~text
Audit:
all supported mutation records

Timeline:
selected customer-facing activity/task/email history
~~~

# Privacy and data minimization

## 136. Audit changes are explicit, not automatic entity snapshots

This is the first major privacy safeguard.

## 137. Facade field summaries avoid copying values

present_fields and revision_fields operate on field names.

## 138. Event payload should still be treated as a public contract

When an event is serialized externally, payload content becomes part of the
integration boundary.

## 139. Audit record_event deliberately does not copy payload

This prevents public event payload from automatically becoming long-lived audit
detail.

## 140. Timeline metadata is projection-specific

Timeline projection selects the metadata needed for customer history.

It does not blindly copy event payload wholesale.

## 141. Context identifiers themselves should remain non-sensitive identifiers

Applications should avoid placing secrets or raw sensitive content into actor or
correlation identifiers.

Detailed Security & Privacy guidance arrives in Chapter 32.

# Testing context, events and audit

## 142. Context tests should cover

~~~text
trimmed actor/correlation
blank rejection
typed causation
partial with_context overrides
explicit clearing with None
shared backend
~~~

## 143. Event-derived context tests should cover

~~~text
actor propagation
existing correlation propagation
missing correlation fallback to parent EventId
direct causation
multi-hop causation chain
~~~

## 144. DomainEvent tests should cover

~~~text
immutable envelope
UTC time
event-type normalization
schema_version validation
payload/metadata freezing
serialization round trip
~~~

## 145. Registry tests should cover

~~~text
exact type/version resolution
duplicate registration
multiple versions
latest version
fresh default registry
unsupported serialization
~~~

## 146. EventBus tests should cover

~~~text
exact-type subscription
subscription order
duplicate-subscription idempotency
unsubscribe
handler exception propagation
~~~

## 147. Transaction-event tests should cover

~~~text
event staged before commit
no publication before commit
rollback clears events
commit publishes
subscriber sees committed state
subscriber failure does not undo source commit
~~~

## 148. Audit tests should cover

~~~text
append-only records
actor propagation
correlation propagation
entity/action identity
explicit minimized changes
event payload not copied by default
correlation queries
~~~

## 149. Timeline tests should cover

~~~text
supported event projection
unsupported event ignored
actor/correlation propagation
source EventId identity
business occurrence timestamps
replay idempotency
rollback atomicity
Contact/Organization history
~~~

## 150. Configuration tests should cover independent switches

~~~text
events off / audit on
events on / audit off
both off with supported Timeline projection
~~~

## Common mistakes

### Treating correlation_id as causation_id

Correlation groups a trace; causation points to the direct parent event.

### Generating a new correlation ID for every child event

Child work should normally preserve the existing trace correlation.

### Losing trace identity when the parent has no correlation

CRMContext.from_event uses the parent EventId as the correlation root.

### Mutating one CRM context globally

Use immutable CRM facade views through with_context or with_event.

### Putting HTTP objects in domain context

CRMContext should stay framework-neutral.

### Publishing events directly from domain services before commit

Facade/runtime transaction staging owns publication order.

### Treating EventBus as a durable broker

It is synchronous and in-process.

### Copying full event payloads into Audit automatically

AuditService intentionally avoids that.

### Assuming Audit stores causation_id

Current AuditEntry stores actor/correlation, not causation.

### Assuming Timeline stores causation_id

Current TimelineEntry also stores actor/correlation only.

### Assuming every Domain Event appears in Timeline

Only selected Activity, Task and Email lifecycle events are projected.

### Disabling events and assuming Timeline is disabled

Timeline projection is independent for supported events.

### Treating Timeline as Audit

Timeline is a customer-history projection; Audit is operational mutation
history.

### Treating Audit as source-of-truth domain state

Audit is historical trace, not the canonical aggregate store.

### Putting secrets in actor/correlation identifiers

Keep contextual identifiers non-secret and stable.

## What you learned

You can now explain:

- CRMConfig and CRMContext;
- actor, correlation and causation semantics;
- config-seeded default context;
- with_context immutable facade views;
- CRMContext.from_event;
- with_event;
- correlation fallback to parent EventId;
- multi-hop causation chains;
- the immutable DomainEvent envelope;
- EventRegistry and EventSerializer governance;
- exact-type in-process subscriptions;
- transactional event staging;
- post-commit publication;
- AuditEntry and AuditService;
- audit PII minimization;
- actor/correlation in Audit;
- Timeline projection;
- actor/correlation in Timeline;
- Timeline EventId-derived replay identity;
- independent events/audit/timeline behavior;
- FastAPI/DRF context bridges;
- post-commit webhook integration.

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
30 Context, Events & Audit     ✅
31 Error Handling              ← NEXT
32 Security & Privacy
~~~

The cross-cutting change path can now be summarized as:

~~~text
Context
  |
  v
CRM command
  |
  v
DomainEvent
  |
  +--> Timeline
  +--> Audit
  +--> pending publication
  |
  v
COMMIT
  |
  v
Subscribers / Webhooks
~~~

## Next

The next chapter is **31 - Error Handling**.

The next architecture is:

~~~text
Domain / Repository / Integration failure
      |
      v
PyCRMKit exception hierarchy
      |
      +--> stable error code
      +--> privacy-safe context
      |
      v
transport adapter
      |
      +--> FastAPI status mapping
      +--> DRF status mapping
      |
      v
public error response
~~~

The next learning question is:

> How does PyCRMKit normalize validation, not-found, conflict, repository and
> integration failures into stable application errors while preserving useful
> diagnostics without leaking database internals or sensitive data?
