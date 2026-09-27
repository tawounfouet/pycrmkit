# Domain Events

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 4 - Communication & Automation**.

Chapter 14 introduced lifecycle events such as:

~~~text
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

Those names are not ad-hoc callbacks. They are occurrences carried by the same
stable DomainEvent envelope used throughout PyCRMKit.

The central question is now:

~~~text
How does PyCRMKit represent, govern, serialize and propagate
domain changes without coupling business domains to consumers?
~~~

## What you will build

You will:

- understand the immutable DomainEvent envelope;
- learn the EventType naming contract;
- distinguish event schema version from the PyCRMKit package version;
- work with immutable JSON-compatible payloads and metadata;
- use EventRegistry to govern exact public event contracts;
- use EventSerializer for deterministic canonical JSON;
- understand the 41 built-in v1 event definitions;
- subscribe to exact event types with crm.events;
- understand synchronous InProcessEventBus behavior;
- propagate actor, correlation and causation;
- create multi-hop event-triggered workflows with crm.with_event(...);
- understand event staging inside a Unit of Work;
- understand commit-before-publication semantics;
- understand subscriber failures after commit;
- distinguish in-process events from durable Webhook delivery.

The mental model is:

~~~text
Domain mutation
      |
      v
CRMRuntime.record_change
      |
      +--> Timeline projection
      +--> Audit entry
      +--> staged DomainEvent
      |
      v
Unit of Work commit
      |
      v
InProcessEventBus
      |
      +--> subscriber A
      +--> subscriber B
      +--> ...
      |
      v
automation / webhook delivery
~~~

## 1. What is a Domain Event?

A Domain Event is an immutable statement that something meaningful happened in
the CRM domain.

Examples:

~~~text
contact.created
task.completed
lead.converted
opportunity.won
email.opened
~~~

An event says:

> this domain fact occurred.

It is not a command asking the domain to do something.

## 2. Event vs command

A command is imperative:

~~~text
CreateContact
CompleteTask
ConvertLead
SendEmail
~~~

A Domain Event is factual:

~~~text
contact.created
task.completed
lead.converted
email.sent
~~~

The command may fail.

The event represents the outcome staged by a successful domain mutation.

## 3. Stable DomainEvent envelope

Every public event uses the same envelope:

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

This separates transport/tracing information from domain-specific payload data.

## 4. EventId

Each event occurrence has a typed EventId.

Two contact.created events still have different EventId values.

EventId identifies the occurrence, not the aggregate.

## 5. EventType

Public event names use EventType.

~~~python
from pycrmkit.events import EventType

event_type = EventType(" Contact.Created ")

assert str(event_type) == "contact.created"
~~~

EventType trims outer whitespace, case-folds to lowercase and validates a dotted
identifier.

## 6. EventType naming contract

The stable pattern requires at least two dotted segments.

Valid examples:

~~~text
contact.created
opportunity.stage_changed
email.delivered
custom_domain.fact_happened
~~~

A single segment such as:

~~~text
created
~~~

is invalid.

Stable error:

~~~text
ValidationError
code = event.type.invalid
~~~

## 7. DomainEvent is immutable

DomainEvent is frozen.

~~~python
event = DomainEvent.create(...)

# assigning to event.aggregate_id is not allowed
~~~

Events represent history, not mutable workflow state.

## 8. Payload and metadata are deeply frozen

payload and metadata are converted to immutable JSON-compatible structures.

~~~python
event = DomainEvent.create(
    ...,
    payload={
        "source": "import",
        "labels": ["vip", "new"],
    },
)

assert event.payload["labels"] == ("vip", "new")
~~~

Nested mutable JSON containers do not remain mutable inside the event.

## 9. JSON-compatible boundary

Payload and metadata are intended for JSON-compatible values.

Arbitrary Python objects are rejected by the JSON freezing layer.

This keeps event contracts portable across:

~~~text
in-process handlers
serialization
signing
webhooks
external consumers
~~~

## 10. schema_version

Every event carries:

~~~text
schema_version >= 1
~~~

DomainEvent.create(...) defaults to schema version 1.

Invalid values raise:

~~~text
ValidationError
code = event.schema_version.invalid
~~~

## 11. Schema version is not package version

These are independent:

~~~text
PyCRMKit package version:
1.0.0

contact.created schema version:
1
~~~

The public contract identity is:

~~~text
(event_type, schema_version)
~~~

## 12. aggregate_type

aggregate_type identifies the family that emitted the event.

Examples:

~~~text
contact
task
opportunity
communication_record
~~~

It is trimmed, case-folded and required.

Blank values raise:

~~~text
event.aggregate_type.invalid
~~~

## 13. aggregate_id

aggregate_id identifies the specific aggregate occurrence.

DomainEvent.create(...) converts the supplied identifier with str(...).

It is trimmed and cannot be blank.

Blank values raise:

~~~text
event.aggregate_id.invalid
~~~

## 14. occurred_at

occurred_at is normalized to UTC.

With an injected FixedClock, event time is deterministic in tests.

## 15. actor_id

actor_id answers:

> who initiated this domain operation?

It is optional.

When present, it is trimmed and cannot be blank.

Blank values raise:

~~~text
event.actor_id.invalid
~~~

## 16. correlation_id

correlation_id answers:

> which broader business/request trace does this event belong to?

It is optional on a standalone event.

Blank values raise:

~~~text
event.correlation_id.invalid
~~~

## 17. causation_id

causation_id answers:

> which direct parent DomainEvent caused this work?

It is either:

~~~text
None
or
EventId
~~~

Another type raises:

~~~text
event.causation_id.invalid
~~~

## 18. payload

payload contains event-specific public facts.

Examples from stable domains include:

~~~text
delivery_status
provider
business_occurred_at
lead_id
opportunity_id
~~~

The generic event infrastructure does not invent domain payload semantics.

## 19. metadata

metadata contains event metadata distinct from domain-specific payload.

It is also frozen and JSON-compatible.

Applications should treat it as part of the governed external boundary when the
event will be serialized or delivered.

## 20. Direct event creation

Lower-level code can create a custom event:

~~~python
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.time import SystemClock
from pycrmkit.events import DomainEvent

event = DomainEvent.create(
    id_factory=UUID4Factory(),
    clock=SystemClock(),
    type="customer.synced",
    aggregate_type="contact",
    aggregate_id="contact-123",
    actor_id="sync-worker",
    correlation_id="sync-run-001",
    payload={"source": "erp"},
)
~~~

Custom event creation is valid.

## 21. Registry validation is not creation validation

This is a key V1 boundary.

DomainEvent.create(...) validates the generic envelope and EventType syntax.

It does not require the event type to exist in EventRegistry.

Therefore:

~~~text
internal/custom event creation
is possible

public governed serialization
requires registry support
~~~

## 22. to_dict()

DomainEvent.to_dict() emits the stable public envelope using JSON-compatible
primitives.

Conversions include:

~~~text
EventId -> UUID string
EventType -> string
datetime -> ISO 8601 string
causation EventId -> UUID string or null
frozen payload -> JSON-compatible containers
~~~

## 23. from_dict()

DomainEvent.from_dict(...) restores the envelope.

Malformed envelope structure is normalized as:

~~~text
ValidationError
code = event.envelope.invalid
~~~

Round trip:

~~~python
restored = DomainEvent.from_dict(
    event.to_dict()
)

assert restored.to_dict() == event.to_dict()
~~~

## 24. EventDefinition

EventDefinition represents one public event contract.

Its identity is:

~~~text
event_type
schema_version
~~~

Example:

~~~python
from pycrmkit.events import EventDefinition

definition = EventDefinition(
    "contact.created",
    1,
)
~~~

## 25. EventRegistry

EventRegistry governs supported public event contracts.

~~~python
from pycrmkit.events import EventRegistry

registry = EventRegistry()

registry.register(
    "contact.created",
    1,
)
~~~

The registry is mutable configuration. EventDefinition values are immutable.

## 26. Exact contract resolution

Registry resolution is exact on:

~~~text
event_type
+
schema_version
~~~

~~~python
definition = registry.resolve(
    "contact.created",
    1,
)
~~~

If only v1 is registered, resolving v2 does not fall back.

It raises:

~~~text
NotFoundError
code = event.registry.definition.not_found
~~~

## 27. Duplicate registration

Registering the same exact pair twice raises:

~~~text
DuplicateError
code = event.registry.definition.duplicate
~~~

## 28. Multiple versions can coexist

This is valid:

~~~python
registry.register(
    "contact.created",
    1,
)

registry.register(
    "contact.created",
    2,
)
~~~

Both contracts coexist explicitly.

## 29. latest()

~~~python
latest = registry.latest(
    "contact.created",
)

assert latest.schema_version == 2
~~~

latest() selects the highest registered version.

It does not upgrade an event automatically.

## 30. Unknown event type

If latest() finds no version:

~~~text
NotFoundError
code = event.registry.event_type.not_found
~~~

## 31. supports()

~~~python
assert registry.supports(
    "contact.created",
    1,
)
~~~

supports() is an exact boolean contract query.

## 32. validate()

~~~python
definition = registry.validate(
    event,
)
~~~

Validation resolves:

~~~text
(event.type, event.schema_version)
~~~

## 33. definitions()

Definitions are listed in deterministic order:

~~~text
event type ASC
schema version ASC
~~~

That makes documentation and diagnostics reproducible.

## 34. default_event_registry()

PyCRMKit exposes:

~~~python
from pycrmkit.events import (
    default_event_registry,
)

registry = default_event_registry()
~~~

It returns a fresh registry containing the stable built-in contracts emitted
through the 0.4 domains.

## 35. Built-in V1 contracts

The stable source registers 41 built-in event types at schema version 1.

Examples:

~~~text
activity.created
contact.created
contact.updated
contact.archived
organization.created
task.completed
lead.converted
opportunity.stage_changed
opportunity.won
pipeline.created
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

## 36. Fresh registry semantics

Each call returns independent registry state:

~~~python
first = default_event_registry()
second = default_event_registry()

assert first is not second
~~~

Adding an application-specific definition to one does not mutate the other.

## 37. EventSerializer

EventSerializer combines:

~~~text
DomainEvent envelope
+
EventRegistry governance
+
canonical JSON
~~~

~~~python
from pycrmkit.events import EventSerializer

serializer = EventSerializer(
    default_event_registry()
)
~~~

## 38. Serializer to_dict()

~~~python
data = serializer.to_dict(
    event,
)
~~~

Before returning data, EventSerializer validates the exact event contract in its
registry.

## 39. Serializer from_dict()

The restore path is:

~~~text
DomainEvent.from_dict
        |
        v
EventRegistry.validate
        |
        v
DomainEvent
~~~

Envelope validity and contract registration are separate checks.

## 40. Deterministic canonical JSON

serializer.dumps(event) uses:

~~~text
ensure_ascii = False
sort_keys    = True
separators   = (",", ":")
~~~

The same public envelope yields deterministic compact JSON.

Useful cases include:

~~~text
stable fixtures
signing
hashing
transport
reproducible tests
~~~

## 41. Unicode remains readable

Because ensure_ascii is false, Unicode payload values are emitted directly
instead of always becoming ASCII escape sequences.

## 42. Invalid JSON

Malformed JSON passed to loads(...) raises:

~~~text
ValidationError
code = event.serialization.invalid_json
~~~

## 43. JSON must contain an object envelope

A top-level JSON array is invalid.

Stable error:

~~~text
ValidationError
code = event.serialization.invalid_envelope
~~~

## 44. Unregistered serialization

Suppose the registry supports:

~~~text
contact.created v1
~~~

These are rejected:

~~~text
contact.updated v1
contact.created v2
~~~

with registry not-found semantics.

## 45. Registry does not transform schemas

V1 EventRegistry can:

~~~text
register
resolve
latest
supports
validate
list definitions
~~~

It does not:

~~~text
migrate v1 to v2
downcast v2 to v1
transform payloads
infer compatibility
~~~

## 46. InProcessEventBus

InProcessEventBus is the built-in synchronous event publisher.

~~~python
from pycrmkit.events import (
    InProcessEventBus,
)

bus = InProcessEventBus()
~~~

## 47. EventPublisher Protocol

The publication protocol is intentionally tiny:

~~~python
class EventPublisher(Protocol):
    def publish(
        self,
        event: DomainEvent,
    ) -> None:
        ...
~~~

A Unit of Work can therefore depend on publication behavior without depending
on one concrete transport.

## 48. EventHandler Protocol

Subscribers are callables:

~~~python
def handler(
    event: DomainEvent,
) -> None:
    ...
~~~

## 49. Exact-type subscriptions

~~~python
bus.subscribe(
    "contact.created",
    handler,
)
~~~

This matches only contact.created.

It does not match contact.updated and there are no wildcard subscriptions in the
V1 in-process bus.

## 50. Subscription order

Handlers run in subscription order:

~~~text
subscribe(first)
subscribe(second)
publish(event)

first(event)
second(event)
~~~

## 51. Duplicate subscription is idempotent

Subscribing the same handler twice to the same EventType still invokes it once
per event.

## 52. unsubscribe()

~~~python
removed = bus.unsubscribe(
    "contact.created",
    handler,
)
~~~

returns True if a subscription existed, otherwise False.

## 53. on() decorator

~~~python
@bus.on("contact.created")
def on_contact_created(event):
    ...
~~~

The original handler is returned by the decorator.

## 54. clear()

The direct bus exposes clear() to remove all subscriptions.

This is useful for explicit process and test lifecycle control.

## 55. Synchronous dispatch

publish(event) invokes handlers synchronously in the current process.

InProcessEventBus does not itself provide:

~~~text
durable queue
background worker
persistent offsets
retry
dead-letter
distributed fan-out
~~~

## 56. Handler failure propagates

If a handler raises RuntimeError, publish(event) raises that RuntimeError.

The bus does not silently swallow subscriber failures.

## 57. crm.events

The stable CRM facade exposes:

~~~text
crm.events.subscribe
crm.events.unsubscribe
crm.events.on
~~~

It does not expose a public crm.events.publish method.

Business events normally come from successful facade mutations.

## 58. Subscribe through CRM

~~~python
captured = []

crm.events.subscribe(
    "contact.created",
    captured.append,
)

crm.contacts.create(
    display_name="Ada Lovelace",
)

assert len(captured) == 1
~~~

The captured object is a DomainEvent.

## 59. Decorator through CRM

~~~python
@crm.events.on(
    "task.completed",
)
def on_completed(event):
    print(event.aggregate_id)
~~~

This delegates to the shared InProcessEventBus.

## 60. Events are staged inside the Unit of Work

Facade mutation does not immediately publish while repository state is still
uncommitted.

Conceptually:

~~~text
mutation
  |
  v
save aggregate in working state
  |
  v
CRMRuntime.record_change
  |
  v
uow.add_event
  |
  v
commit
  |
  v
publish staged events
~~~

## 61. Commit happens before subscriber publication

MemoryUnitOfWork.commit() performs the important ordering:

~~~text
1. snapshot pending events
2. commit working state to MemoryStore
3. mark UoW committed
4. clear pending event list
5. release MemoryStore transaction
6. publish each event synchronously
~~~

## 62. Why the Memory transaction is released first

Subscribers may open a new Unit of Work and read newly committed state.

This supports event-triggered follow-up operations without nested Memory
transactions.

## 63. Subscriber can observe committed state

Conceptually:

~~~python
def on_contact_created(event):
    assert (
        crm.contacts.search(
            ContactQuery(name="Ada")
        ).total
        == 1
    )
~~~

The subscriber runs after the Contact commit.

## 64. Subscriber failure does not roll back source state

Suppose:

~~~text
Contact commit succeeds
        |
        v
contact.created subscriber
        |
        X RuntimeError
~~~

The caller sees the RuntimeError, but the Contact was already committed.

## 65. Exception does not always mean rollback

This is the same boundary used in the Lead Conversion retry chapter.

Generic rule:

~~~text
domain commit
    |
    v
post-commit synchronous subscriber
~~~

An exception from a subscriber occurs after source persistence.

## 66. Rollback before commit discards events

If a Unit of Work never commits:

~~~text
working state discarded
pending events cleared
no event publication
~~~

Pending DomainEvents participate in orchestration around the transaction
boundary.

## 67. events_enabled

CRMConfig exposes:

~~~python
CRMConfig(
    events_enabled=True,
    audit_enabled=True,
)
~~~

With events_enabled=False, facade changes are not staged for event-bus
publication.

## 68. Audit is independently configurable

These are valid:

~~~text
events disabled
audit enabled

events enabled
audit disabled
~~~

Audit and in-process event publication are separate capabilities.

## 69. Timeline projection is distinct

CRMRuntime.record_change also checks TimelineProjector support.

For supported events, Timeline projection occurs inside the source Unit of Work.

Timeline is therefore not modeled as a normal post-commit asynchronous
subscriber.

## 70. CRMContext

Cross-cutting operation context contains:

~~~text
actor_id
correlation_id
causation_id
~~~

Facade mutations copy this context into emitted event envelopes.

## 71. with_context()

~~~python
scoped = crm.with_context(
    actor_id="agent-7",
    correlation_id="request-900",
)
~~~

The returned CRM view shares:

~~~text
backend
event bus
integrations
~~~

while carrying new operation context.

## 72. Root event

A root mutation through the scoped CRM emits:

~~~text
actor_id       = agent-7
correlation_id = request-900
causation_id   = None
~~~

unless causation was explicitly supplied.

## 73. CRMContext.from_event()

For child work caused by a parent event:

~~~python
child_context = CRMContext.from_event(
    parent,
)
~~~

the rule is:

~~~text
actor_id       = parent.actor_id
correlation_id = parent.correlation_id
                 or str(parent.id)
causation_id   = parent.id
~~~

## 74. crm.with_event()

The high-level convenience:

~~~python
child_crm = crm.with_event(
    parent_event,
)
~~~

uses CRMContext.from_event(parent_event) while preserving the same backend and
integrations.

## 75. Child event trace

~~~python
task = crm.with_event(
    root,
).tasks.create(
    title="Follow up",
)
~~~

The resulting task.created event inherits actor and correlation and points
causation_id to root.id.

## 76. Correlation fallback

If the parent has no correlation_id:

~~~text
child correlation_id = str(parent.id)
~~~

The parent's own EventId becomes the trace root.

## 77. Multi-hop chain

For:

~~~text
A causes B
B causes C
~~~

with request correlation request-1:

~~~text
A:
correlation = request-1
causation   = None

B:
correlation = request-1
causation   = A.id

C:
correlation = request-1
causation   = B.id
~~~

Correlation stays stable. Causation always references the direct parent.

## 78. Actor propagation

CRMContext.from_event preserves parent.actor_id for event-triggered follow-up
work.

This keeps attribution coherent across an automation chain.

## 79. Serialization preserves tracing

DomainEvent.to_dict() and EventSerializer preserve:

~~~text
actor_id
correlation_id
causation_id
~~~

Causal information therefore survives the serialization boundary.

## 80. Complete envelope example

~~~python
from datetime import UTC, datetime

from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.time import FixedClock
from pycrmkit.events import DomainEvent

clock = FixedClock(
    datetime(2026, 9, 28, 11, 0, tzinfo=UTC)
)

event = DomainEvent.create(
    id_factory=UUID4Factory(),
    clock=clock,
    type="contact.created",
    aggregate_type="Contact",
    aggregate_id="contact-123",
    actor_id="agent-7",
    correlation_id="request-900",
    payload={
        "source": "guide",
        "labels": ["vip", "new"],
    },
    metadata={
        "origin": "zero-to-hero",
    },
)

assert str(event.type) == "contact.created"
assert event.aggregate_type == "contact"
assert event.payload["labels"] == (
    "vip",
    "new",
)
~~~

## 81. Registry and serializer example

~~~python
from pycrmkit.events import (
    EventRegistry,
    EventSerializer,
)

registry = EventRegistry()
registry.register(
    "contact.created",
    1,
)
registry.register(
    "contact.created",
    2,
)

assert (
    registry.latest(
        "contact.created"
    ).schema_version
    == 2
)

serializer = EventSerializer(
    registry,
)

encoded = serializer.dumps(
    event,
)

restored = serializer.loads(
    encoded,
)

assert (
    restored.to_dict()
    == event.to_dict()
)
~~~

## 82. Built-in serializer example

~~~python
from pycrmkit.events import (
    EventSerializer,
    default_event_registry,
)

serializer = EventSerializer(
    default_event_registry()
)

encoded = serializer.dumps(
    event,
)
~~~

contact.created v1 is part of the built-in registry.

## 83. Custom event serialization

A custom event becomes serializable after its contract is registered:

~~~python
custom_registry = EventRegistry()

custom_registry.register(
    "customer.synced",
    1,
)

custom_serializer = EventSerializer(
    custom_registry,
)
~~~

## 84. Bus ordering example

~~~python
from pycrmkit.events import (
    InProcessEventBus,
)

bus = InProcessEventBus()
calls = []

def first(event):
    calls.append("first")

def second(event):
    calls.append("second")

bus.subscribe(
    "contact.created",
    first,
)

bus.subscribe(
    "contact.created",
    second,
)

bus.publish(
    event,
)

assert calls == [
    "first",
    "second",
]
~~~

## 85. Complete correlation example

~~~python
crm = CRM.memory(
    clock=clock,
).with_context(
    actor_id="agent-7",
    correlation_id="request-900",
)

contacts = []
tasks = []
completed = []

crm.events.subscribe(
    "contact.created",
    contacts.append,
)

crm.events.subscribe(
    "task.created",
    tasks.append,
)

crm.events.subscribe(
    "task.completed",
    completed.append,
)

crm.contacts.create(
    display_name="Trace Root",
)

root = contacts[0]

task = crm.with_event(
    root,
).tasks.create(
    title="Follow up",
)

child = tasks[0]

crm.with_event(
    child,
).tasks.complete(
    task.id,
)

grandchild = completed[0]

assert child.correlation_id == "request-900"
assert child.causation_id == root.id

assert grandchild.correlation_id == "request-900"
assert grandchild.causation_id == child.id
~~~

## 86. Post-commit visibility example

~~~python
seen = []

def observe(event):
    seen.append(
        crm.contacts.search(
            ContactQuery(
                name="Committed Contact",
            )
        ).total
    )

crm.events.subscribe(
    "contact.created",
    observe,
)

crm.contacts.create(
    display_name="Committed Contact",
)

assert seen == [1]
~~~

## 87. Subscriber failure example

~~~python
def fail(event):
    raise RuntimeError(
        "subscriber failed"
    )

crm.events.subscribe(
    "contact.created",
    fail,
)

try:
    crm.contacts.create(
        display_name="Still Committed",
    )
except RuntimeError:
    pass

assert (
    crm.contacts.search(
        ContactQuery(
            name="Still Committed",
        )
    ).total
    == 1
)
~~~

## 88. Event payload privacy is domain-specific

The event infrastructure guarantees envelope validation, immutability and
JSON-compatible serialization.

It does not automatically know which business values are sensitive.

Privacy decisions belong to the emitting domain.

Chapter 14 showed that Communication lifecycle payloads deliberately omit
recipient addresses and message bodies.

Custom event producers must make equivalent decisions deliberately.

## 89. Domain Events vs Audit

~~~text
DomainEvent
= fact for consumers and automation

AuditEntry
= governance/history record of mutation
~~~

PyCRMKit can derive both from one facade mutation while allowing them to be
enabled independently.

## 90. Domain Events vs Timeline

~~~text
DomainEvent
= occurrence envelope

TimelineEntry
= customer-history read model
~~~

Some event types project into Timeline transactionally.

Not every DomainEvent becomes a TimelineEntry.

## 91. Domain Events vs Webhooks

~~~text
DomainEvent
= domain occurrence

Webhook
= external HTTP delivery of selected events
~~~

Webhooks add:

~~~text
subscriptions
signing
HTTP transport
retry
delivery state
dead-letter behavior
~~~

Those belong to chapter 16.

## 92. In-process bus is not a durable queue

Do not treat InProcessEventBus as:

~~~text
Kafka
RabbitMQ
SQS
database outbox
durable cross-process messaging
~~~

It is synchronous and process-local.

## 93. Registry is not a broker

~~~text
EventRegistry
= what public event schema is supported?

InProcessEventBus
= which in-process handler receives an occurrence?
~~~

These are orthogonal responsibilities.

## 94. Serializer is not persistence

EventSerializer does not:

~~~text
persist events
retry delivery
claim work
deduplicate consumers
manage offsets
~~~

It only governs conversion to and from deterministic public JSON.

## Common mistakes

### Treating DomainEvent as mutable state

Events represent facts and are immutable.

### Using an undotted event name

Use contact.created rather than created.

### Tying schema_version to PyCRMKit package version

They evolve independently.

### Assuming custom events must exist in the default registry to be created

Event creation and governed serialization are separate boundaries.

### Assuming EventRegistry upgrades schemas

It resolves exact contracts; it does not transform versions.

### Serializing without registering the contract

EventSerializer validates the exact type/version pair.

### Assuming subscriber matching is hierarchical

contact.created does not match contact.updated or contact.*.

### Assuming subscribers run before commit

Memory Unit of Work commits and releases its transaction before publication.

### Assuming subscriber failure rolls back the source mutation

The source state is already committed.

### Using InProcessEventBus as durable messaging

It is synchronous and process-local.

### Confusing correlation with causation

Correlation groups the trace; causation points to the direct parent event.

### Creating a new correlation ID for every child event

crm.with_event(parent) preserves the trace.

### Dropping actor context in event-triggered work

CRMContext.from_event preserves the actor.

### Putting sensitive data in custom payloads because JSON supports it

JSON compatibility is not a privacy policy.

### Treating Timeline as an asynchronous subscriber

Supported Timeline projections happen inside the source Unit of Work.

### Treating EventRegistry as a publisher

Registry governance and dispatch are separate.

## Testing event-driven workflows

A strong test suite separates four concerns.

Envelope and serialization:

~~~text
EventType normalization
immutable payload
schema version
registry validation
deterministic JSON
round trip
~~~

Bus behavior:

~~~text
exact matching
subscription order
duplicate subscription
unsubscribe
handler failure
~~~

Trace propagation:

~~~text
actor
correlation
causation
multi-hop
~~~

Transaction semantics:

~~~text
state committed before subscriber
subscriber can open follow-up work
subscriber failure does not roll back source state
~~~

## What you learned

You can now explain and use:

- EventId;
- EventType;
- immutable DomainEvent envelopes;
- frozen JSON-compatible payload and metadata;
- schema versioning;
- aggregate identity fields;
- actor/correlation/causation;
- DomainEvent.create;
- to_dict and from_dict;
- EventDefinition;
- exact type/version contracts;
- EventRegistry register/resolve/latest/supports/validate/definitions;
- default_event_registry;
- the 41 built-in v1 contracts;
- EventSerializer;
- deterministic compact Unicode JSON;
- custom event registration;
- EventPublisher;
- EventHandler;
- InProcessEventBus;
- exact synchronous subscriptions;
- stable subscription order;
- idempotent duplicate subscriptions;
- unsubscribe, decorator and clear;
- crm.events subscribe/unsubscribe/on;
- Unit-of-Work event staging;
- post-commit publication;
- subscriber access to committed state;
- post-commit failure semantics;
- CRMConfig.events_enabled;
- event/audit independence;
- transactional Timeline projection;
- CRMContext;
- with_context;
- CRMContext.from_event;
- crm.with_event;
- correlation fallback;
- multi-hop causal tracing;
- serialization of trace fields;
- boundaries among Domain Events, Audit, Timeline and Webhooks.

## LEVEL 4 in progress

The automation chain is now visible:

~~~text
Domain mutation
      |
      v
DomainEvent
      |
      +--> in-process subscribers
      +--> governed serialization
      |
      v
external delivery boundary
~~~

One chapter remains to complete LEVEL 4.

## Next

The next chapter is **16 - Webhooks**.

It will take governed DomainEvents across the external HTTP boundary:

~~~text
DomainEvent
    |
    v
Webhook subscription matching
    |
    v
EventSerializer canonical JSON
    |
    v
HMAC-SHA256 signature
    |
    v
WebhookTransport
    |
    +--> success
    +--> retry
    +--> dead letter
~~~

The next learning question is:

> How does PyCRMKit deliver selected committed events to external systems
> idempotently and safely without turning business domains into HTTP clients?
