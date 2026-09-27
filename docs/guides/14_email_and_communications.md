# Email & Communications

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter begins **LEVEL 4 - Communication & Automation**.

LEVEL 3 established the Sales Foundation:

~~~text
Lead
  ↓
Opportunity
  ↓
Pipeline
  ↓
Lead Conversion
~~~

The CRM can now model who is being pursued, what commercial outcome matters and
how that outcome progresses.

The next problem is communication.

The central question becomes:

~~~text
How does a CRM represent, send and track email
without coupling the domain to SMTP, Resend or another provider?
~~~

PyCRMKit answers this by separating **communication intent**, **transport
submission**, **CRM history**, **delivery lifecycle** and **Timeline
projection**.

## What you will build

You will:

- model provider-neutral email addresses, recipients and content;
- configure a CRM with an EmailProvider and sender;
- send an outbound email transactionally;
- understand CommunicationIntent and DeliveryAttempt;
- distinguish provider acceptance from mailbox delivery;
- persist CommunicationRecord history;
- record delivered/opened/clicked/bounced/failed callbacks;
- make provider callbacks idempotent through external event IDs;
- protect current state from older out-of-order callbacks;
- query communication history for Contacts and Organizations;
- inspect append-only delivery history;
- project communication lifecycle into Timeline;
- use provider-neutral templates;
- understand SMTP and Resend as adapters, not domain concepts;
- understand outbound-send idempotency boundaries.

By the end of this chapter, the mental model is:

~~~text
Business need
    |
    v
CommunicationIntent
    |
    v
EmailMessage
    |
    v
EmailProvider
    |
    v
DeliveryAttempt
    |
    v
CommunicationRecord
    |
    +--> EmailDeliveryEvent history
    |
    v
Timeline
~~~

## 1. Why Communication is its own domain

A CRM email is more than an Activity and more than an SMTP request.

It has at least five distinct concerns:

~~~text
1. What do we intend to communicate?
2. What did the transport provider accept or reject?
3. What should the CRM remember as relationship history?
4. What later delivery events did the provider report?
5. How should that history appear in the customer Timeline?
~~~

Collapsing those concerns into one object makes provider details leak into the
CRM domain and makes lifecycle state ambiguous.

PyCRMKit keeps them separate.

## 2. Stable Communication architecture

The stable V1 architecture is:

~~~text
CommunicationIntent
        |
        v
EmailDeliveryService
        |
        v
EmailProvider
        |
        v
DeliveryAttempt
        |
        v
CommunicationRecord
        |
        v
EmailDeliveryEvent history
        |
        v
TimelineEntryKind.COMMUNICATION
~~~

These objects deliberately do not mean the same thing.

## 3. Communication is not mirrored as Activity(email)

PyCRMKit does **not** automatically create:

~~~text
Activity(type="email")
~~~

for each Communication.

The architecture decision is:

~~~text
CommunicationRecord
= authoritative communication-history entity

Timeline
= cross-domain relationship-history view

Activity
= separate source domain
~~~

This avoids duplicating:

- identity;
- timestamps;
- provider state;
- delivery lifecycle;
- history.

Activity and Communication converge only in Timeline.

## 4. Current channel scope

The Communication foundation defines:

~~~python
from pycrmkit.communication import CommunicationChannel

assert CommunicationChannel.EMAIL.value == "email"
~~~

Stable V1 is email-first.

CommunicationChannel currently exposes EMAIL as the supported channel in this
domain foundation.

## 5. Communication direction

~~~python
from pycrmkit.communication import CommunicationDirection

assert CommunicationDirection.OUTBOUND.value == "outbound"
assert CommunicationDirection.INBOUND.value == "inbound"
~~~

However, CommunicationIntent in the stable 0.4 foundation is specifically an
**outbound** intent.

Constructing an inbound CommunicationIntent raises:

~~~text
ValidationError
code = communication.intent.direction.invalid
~~~

CommunicationRecord itself can represent direction independently.

## 6. CommunicationAddress

A provider-neutral address is represented by:

~~~python
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
)

address = CommunicationAddress(
    CommunicationChannel.EMAIL,
    " Ada@Example.COM ",
)

assert address.value == "Ada@Example.COM"
assert address.normalized == "ada@example.com"
~~~

The original cleaned value and normalized identity are separate.

## 7. Email-address normalization

Stable V1 applies a deliberately small provider-neutral normalization contract.

For email:

~~~text
Unicode NFKC
trim
single-line whitespace cleanup
exactly one @
no whitespace
non-empty local part
non-empty domain
domain cannot begin/end with "."
case-fold local part and domain for normalized identity
~~~

This is not a full RFC mailbox parser and does not perform provider-specific
rewriting.

## 8. Invalid email address

Examples such as:

~~~text
""
"not-an-email"
"a @example.com"
"@example.com"
"a@"
"a@.example"
"a@example."
~~~

are rejected by CommunicationAddress.

The stable error is:

~~~text
ValidationError
code = communication.address.email.invalid
~~~

An empty address uses:

~~~text
communication.address.required
~~~

## 9. CommunicationRecipient

A recipient combines:

~~~text
address
optional display_name
optional CRM EntityReference
~~~

Example:

~~~python
from pycrmkit.communication import CommunicationRecipient
from pycrmkit.core.references import EntityReference

contact_ref = EntityReference(
    "contact",
    contact.id,
)

recipient = CommunicationRecipient(
    address=CommunicationAddress(
        CommunicationChannel.EMAIL,
        "ada@example.com",
    ),
    display_name="Ada Lovelace",
    reference=contact_ref,
)
~~~

The reference is what connects the communication to CRM history.

## 10. Recipient display name

display_name is:

~~~text
Unicode NFKC normalized
trimmed
internal whitespace collapsed
blank -> None
maximum 300 characters
~~~

It does not alter the normalized email identity.

## 11. Recipient reference

reference must be an EntityReference when supplied.

This makes Communication reusable across CRM entity kinds without introducing a
Contact-only dependency into the value object.

## 12. Recipient uniqueness

A Communication requires at least one recipient.

Recipients are unique by:

~~~text
(channel, normalized address)
~~~

Therefore:

~~~text
Ada@Example.com
ada@example.COM
~~~

represent the same email-recipient identity.

Duplicates raise:

~~~text
ValidationError
code = communication.recipient.duplicate
~~~

## 13. CommunicationContent

Provider-neutral content is:

~~~python
from pycrmkit.communication import CommunicationContent

content = CommunicationContent(
    subject="  Enterprise   proposal ",
    text_body="Hello Ada,\nYour proposal is ready.",
    html_body="<p>Hello Ada</p>",
)

assert content.subject == "Enterprise proposal"
~~~

The domain does not store provider-specific MIME or SDK payloads here.

## 14. Content body requirement

At least one of:

~~~text
text_body
html_body
~~~

must be present after normalization.

A subject-only CommunicationContent is invalid:

~~~text
ValidationError
code = communication.content.body.required
~~~

## 15. Subject normalization

subject is:

~~~text
Unicode NFKC
single-line
trimmed
internal whitespace collapsed
blank -> None
maximum 500 characters
~~~

## 16. Body normalization

text_body and html_body are:

~~~text
Unicode NFKC
outer whitespace trimmed
internal/newline structure otherwise preserved
blank -> None
maximum 1,000,000 characters each
~~~

The domain does not sanitize or rewrite HTML content at this layer.

## 17. CommunicationIntent

CommunicationIntent is the provider-independent request to communicate.

It contains:

~~~text
id
created_at / updated_at
channel
recipients
content
direction
status
references
idempotency_key
metadata
queued_at
cancelled_at
~~~

Its identity is a typed CommunicationIntentId.

## 18. Intent lifecycle

Stable intent lifecycle:

~~~text
DRAFT
  |
  +--> QUEUED
  |
  +--> CANCELLED

QUEUED
  |
  +--> CANCELLED
~~~

The intent itself does **not** become SENT or DELIVERED.

That distinction is essential.

Transport and delivery state live elsewhere.

## 19. Queue an Intent

At the lower domain layer:

~~~python
intent.queue(clock.now())

assert intent.status.value == "queued"
assert intent.queued_at is not None
~~~

Only DRAFT may transition to QUEUED.

Invalid transition:

~~~text
InvalidStateError
code = communication.intent.transition.invalid
~~~

## 20. Cancel an Intent

DRAFT or QUEUED may be cancelled:

~~~python
intent.cancel(clock.now())
~~~

CANCELLED requires cancelled_at.

Transition timestamps cannot predate entity creation.

## 21. crm.email.send creates and queues the Intent automatically

Most applications do not construct CommunicationIntent directly for ordinary
outbound email.

The high-level facade:

~~~text
crm.email.send(...)
~~~

creates an outbound DRAFT intent, immediately queues it, persists it and invokes
the configured provider in one CRM operation.

## 22. Configure email dependencies

CRM.memory accepts:

~~~text
email_provider
email_sender
template_renderer
~~~

Example:

~~~python
crm = CRM.memory(
    email_provider=provider,
    email_sender=CommunicationAddress(
        CommunicationChannel.EMAIL,
        "sales@example.com",
    ),
)
~~~

CRM.with_context(...) preserves these dependencies.

## 23. EmailProvider is a Protocol

The transport seam is:

~~~python
class EmailProvider(Protocol):
    def send(
        self,
        message: EmailMessage,
    ) -> EmailProviderResult:
        ...
~~~

The Communication domain therefore does not import SMTP, Resend, credentials,
HTTP clients or provider SDKs.

## 24. A minimal provider

A custom provider can be extremely small:

~~~python
from pycrmkit.communication import (
    EmailDeliveryStatus,
    EmailProviderResult,
)

class MyProvider:
    def send(self, message):
        return EmailProviderResult(
            provider="my-provider",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="provider-123",
        )
~~~

The provider receives an EmailMessage rather than CommunicationIntent directly.

## 25. EmailMessage

EmailMessage is the immutable provider-facing DTO.

It contains:

~~~text
intent_id
sender
recipients
content
idempotency_key
metadata
~~~

CRM EntityReference values are deliberately not copied into the provider
message.

The provider needs transport data, not the CRM relationship graph.

## 26. Sender validation

EmailMessage sender must be:

~~~text
CommunicationAddress(channel=email)
~~~

The facade requires either:

- sender passed to crm.email.send(...); or
- default email_sender configured on CRM.

If neither exists:

~~~text
ValidationError
code = communication.email.sender.required
~~~

## 27. Missing provider

crm.email.send requires a configured EmailProvider.

Without one:

~~~text
IntegrationError
code = communication.email.provider.required
~~~

The failure occurs before the Unit of Work send workflow begins.

## 28. EmailProviderResult

Every provider returns the normalized transport result:

~~~text
provider
status
provider_message_id?
provider_metadata
failure_code?
~~~

status is one of:

~~~text
accepted
failed
~~~

## 29. ACCEPTED is not DELIVERED

This is one of the most important concepts in the Communication model.

~~~text
EmailProviderResult.ACCEPTED
= provider accepted transport submission

NOT
= recipient mailbox delivered

NOT
= opened

NOT
= clicked
~~~

Downstream lifecycle is recorded later through EmailDeliveryEvent callbacks.

## 30. Provider result invariants

For ACCEPTED:

~~~text
failure_code must be None
provider_message_id may be present
~~~

For FAILED:

~~~text
provider_message_id must be None
failure_code may be present
~~~

Violations raise typed Communication validation errors.

## 31. Provider name

provider is required, Unicode-normalized and whitespace-collapsed.

Maximum length:

~~~text
120
~~~

This name participates in provider message / callback correlation.

## 32. EmailDeliveryService

EmailDeliveryService converts:

~~~text
queued CommunicationIntent
        +
sender
        |
        v
EmailMessage
        |
        v
EmailProvider.send
        |
        v
EmailProviderResult
        |
        v
DeliveryAttempt
~~~

It is provider-independent application/domain orchestration.

## 33. Delivery requires QUEUED Intent

Calling EmailDeliveryService.send with a DRAFT Intent raises:

~~~text
InvalidStateError
code = communication.email.intent.not_queued
~~~

The provider is not called.

## 34. Provider contract violation

If an EmailProvider returns something other than EmailProviderResult:

~~~text
IntegrationError
code = communication.email.provider.result.invalid
~~~

Provider adapters must normalize their result into the stable contract.

## 35. DeliveryAttempt

DeliveryAttempt represents one transport submission.

It contains:

~~~text
intent_id
attempt_number
attempted_at
status
provider
provider_message_id
failure_code
completed_at
metadata
~~~

Typed identity:

~~~text
DeliveryAttemptId
~~~

## 36. DeliveryAttempt lifecycle

~~~text
PENDING
  |
  +--> ACCEPTED
  |
  +--> FAILED
~~~

PENDING is internal construction state.

An accepted provider result maps to ACCEPTED.

A failed provider result maps to FAILED.

## 37. Attempt number

attempt_number must be a positive integer:

~~~text
1, 2, 3, ...
~~~

The current crm.email.send workflow creates the first provider attempt.

EmailDeliveryService supports an explicit attempt_number for lower-level
orchestration.

## 38. ACCEPTED attempt

An accepted attempt has:

~~~text
status = accepted
completed_at != None
failure_code = None
provider_message_id = optional provider identifier
~~~

Provider acceptance does not mutate CommunicationIntent out of QUEUED.

## 39. FAILED attempt

A failed attempt has:

~~~text
status = failed
completed_at != None
provider_message_id = None
failure_code = optional normalized code
~~~

A normalized provider rejection therefore becomes persisted CRM history instead
of automatically raising from crm.email.send.

## 40. Intent remains QUEUED after provider attempt

This can look surprising at first.

~~~text
CommunicationIntent.status = QUEUED
DeliveryAttempt.status     = ACCEPTED
CommunicationRecord.status = SENT
~~~

These are three different state machines.

The Intent says:

> this communication was submitted for delivery.

The Attempt says:

> this provider accepted the transport submission.

The Record says:

> the CRM's current delivery-history state is sent.

## 41. Send direct content

A full direct-content send:

~~~python
record = crm.email.send(
    to=(
        CommunicationRecipient(
            CommunicationAddress(
                CommunicationChannel.EMAIL,
                "ada@example.com",
            ),
            display_name="Ada Lovelace",
            reference=EntityReference(
                "contact",
                contact.id,
            ),
        ),
    ),
    content=CommunicationContent(
        subject="Proposal",
        text_body="Your proposal is ready.",
    ),
    idempotency_key="proposal-001",
)
~~~

The return value is a CommunicationRecord.

## 42. Exactly one content source

crm.email.send accepts either:

~~~text
content
OR
template
~~~

but not both and not neither.

Invalid choice:

~~~text
ValidationError
code = communication.email.content.choice_invalid
~~~

## 43. CommunicationRecord

CommunicationRecord is the authoritative CRM communication-history entity.

It contains:

~~~text
id
channel
direction
occurred_at
counterparties
subject
references
intent_id
delivery_attempt_id
external_id
delivery_status
last_delivery_event_at
metadata
~~~

Notably, it does **not** duplicate the email body.

## 44. Why bodies are not copied into CommunicationRecord

The stable model keeps provider-independent content on CommunicationIntent.

CommunicationRecord is relationship-history state.

This avoids duplicating large or sensitive content just to support customer
history queries.

## 45. Record counterparties

For outbound email, counterparties are the normalized recipient addresses.

They must:

- exist;
- match the record channel;
- be unique by normalized address.

## 46. Record references

The send facade builds record references from:

~~~text
recipient.reference values
+
explicit references passed to send()
~~~

Duplicates are removed while preserving the resulting reference set.

This enables CRM history lookup.

## 47. Contact-linked send

If a recipient references a Contact:

~~~python
reference = EntityReference(
    "contact",
    contact.id,
)

recipient = CommunicationRecipient(
    CommunicationAddress(
        CommunicationChannel.EMAIL,
        "ada@example.com",
    ),
    reference=reference,
)
~~~

then:

~~~python
page = crm.email.for_contact(contact.id)

assert page.items[0].id == record.id
~~~

## 48. Organization-linked send

The same model supports Organization history.

~~~python
organization_ref = EntityReference(
    "organization",
    organization.id,
)

record = crm.email.send(
    to=(recipient,),
    content=content,
    references=(organization_ref,),
)

assert (
    crm.email.for_organization(
        organization.id,
    ).items[0].id
    == record.id
)
~~~

## 49. Communication history ordering

The official Memory repository orders records for a reference by:

~~~text
occurred_at DESC
id ASC for equal timestamps
~~~

Pagination uses exact OffsetPageRequest semantics.

## 50. Get one CommunicationRecord

~~~python
stored = crm.email.get(record.id)

assert stored == record
~~~

Missing records raise normal repository not-found semantics:

~~~text
communication.record.not_found
~~~

## 51. Immediate send lifecycle events

crm.email.send always creates a normalized QUEUED history event before provider
submission.

Then provider result creates one of:

~~~text
email.sent
email.failed
~~~

Therefore a successful accepted submission produces:

~~~text
email.queued
email.sent
~~~

A normalized provider failure produces:

~~~text
email.queued
email.failed
~~~

## 52. EmailDeliveryEventType

Stable normalized lifecycle types:

~~~text
QUEUED
SENT
DELIVERED
OPENED
CLICKED
BOUNCED
FAILED
~~~

Each maps to a public event name:

~~~text
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

## 53. EmailDeliveryEvent

One append-only lifecycle occurrence records:

~~~text
id
intent_id
event_type
occurred_at
recorded_at
delivery_attempt_id?
provider?
provider_message_id?
external_event_id?
recipient?
failure_code?
metadata
~~~

It has typed EmailDeliveryEventId identity.

## 54. occurred_at vs recorded_at

Delivery history deliberately carries two clocks.

~~~text
occurred_at
= business/provider occurrence time

recorded_at
= when this CRM recorded the callback
~~~

This distinction is what allows out-of-order callback ingestion without losing
history.

## 55. QUEUED event is special

QUEUED belongs to the Intent side of the lifecycle.

It cannot carry:

~~~text
delivery_attempt_id
provider
provider_message_id
failure_code
~~~

The queued event represents local submission readiness, before provider outcome.

## 56. Provider context for non-QUEUED events

Every non-queued EmailDeliveryEvent requires:

~~~text
delivery_attempt_id
provider
~~~

Downstream delivery events additionally need provider correlation.

## 57. Provider message ID for downstream events

These types require provider_message_id:

~~~text
DELIVERED
OPENED
CLICKED
BOUNCED
~~~

because they represent lifecycle occurrences correlated to a provider
submission.

## 58. failure_code

failure_code is valid only for:

~~~text
BOUNCED
FAILED
~~~

It is not valid for SENT, DELIVERED, OPENED or CLICKED.

## 59. CommunicationRecord delivery state

The record created after immediate provider outcome has:

~~~text
delivery_status = SENT
or
delivery_status = FAILED
~~~

It also stores:

~~~text
last_delivery_event_at
~~~

with the business occurrence time for the current state.

QUEUED is intentionally not a valid CommunicationRecord.delivery_status.

## 60. Provider callbacks

Downstream provider lifecycle is ingested through:

~~~text
crm.email.record_delivery_event(...)
~~~

The public callback types are:

~~~text
delivered
opened
clicked
bounced
failed
~~~

Trying to ingest queued or sent through this callback method raises:

~~~text
ValidationError
code = communication.email.callback.type.invalid
~~~

## 61. Record DELIVERED

~~~python
event = crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-123",
    event_type=EmailDeliveryEventType.DELIVERED,
    occurred_at=clock.now(),
    external_event_id="evt-delivered-001",
)
~~~

The callback is correlated to the existing DeliveryAttempt using:

~~~text
provider
+
provider_message_id
~~~

## 62. Unknown provider message

If callback correlation cannot find a DeliveryAttempt:

~~~text
NotFoundError
code = communication.delivery.provider_message_not_found
~~~

A callback cannot manufacture a new CommunicationRecord.

## 63. Missing record for known attempt

If the attempt exists but its CommunicationRecord does not:

~~~text
NotFoundError
code = communication.record.attempt_not_found
~~~

This identifies persistence inconsistency explicitly.

## 64. external_event_id enables callback replay

Provider callbacks can supply an external event identity:

~~~text
external_event_id
~~~

The repository indexes it by:

~~~text
normalized provider
+
external event ID
~~~

This gives replay protection for provider notifications.

## 65. Idempotent callback replay

First callback:

~~~text
provider = fake
provider_message_id = msg-123
event_type = opened
external_event_id = evt-999
~~~

A repeated callback with the same provider external ID, event type and provider
message ID returns the existing EmailDeliveryEvent.

It does not:

- append another history event;
- mutate the record again;
- emit another lifecycle DomainEvent.

## 66. Conflicting external callback ID

If the same external_event_id is reused for a different lifecycle type or
provider message ID:

~~~text
DuplicateError
code = communication.delivery_event.external_id.conflict
~~~

This prevents one provider callback identity from representing two different
lifecycle occurrences.

## 67. Callback replay without external ID

Without external_event_id, the facade does not have provider-callback identity
to deduplicate the notification.

Applications should therefore pass a stable provider event ID whenever the
provider supplies one.

## 68. Append-only delivery history

crm.email.delivery_history(record.id) returns the normalized lifecycle events
for the record's Intent.

Example accepted + callbacks:

~~~text
email.queued
email.sent
email.delivered
email.opened
email.clicked
~~~

History remains append-only even when callbacks arrive late.

## 69. Delivery-history ordering

Memory delivery history is ordered by:

~~~text
occurred_at DESC
id ASC for equal timestamps
~~~

So the newest business occurrence appears first.

## 70. Out-of-order callback protection

Suppose current state is:

~~~text
OPENED at 10:04
~~~

Then a late callback arrives:

~~~text
DELIVERED occurred at 10:03
recorded at 10:05
~~~

The event is preserved in append-only history.

But CommunicationRecord remains:

~~~text
delivery_status = OPENED
last_delivery_event_at = 10:04
~~~

The older business event does not regress current state.

## 71. recorded_at can still advance record.updated_at

Even when an older occurred_at does not replace current delivery state, a newer
recorded_at can advance CommunicationRecord.updated_at.

This records the fact that the CRM ingested new history without falsifying the
current business state.

## 72. Equal occurrence timestamps

The aggregate update rule accepts an event whose occurred_at is equal to the
current last_delivery_event_at.

Stable V1's no-regression guarantee is therefore temporal:

~~~text
older occurred_at
-> cannot replace current state
~~~

It is not a semantic ranking such as CLICKED > OPENED > DELIVERED.

## 73. Provider failure is persisted, not necessarily raised

A provider can return:

~~~python
EmailProviderResult(
    provider="fake",
    status=EmailDeliveryStatus.FAILED,
    failure_code="fake.rejected",
)
~~~

crm.email.send then returns a CommunicationRecord whose:

~~~text
delivery_status = FAILED
external_id = None
~~~

and history contains email.failed.

This is a normalized transport outcome, not an IntegrationError.

## 74. Exceptions vs normalized failure

The boundary is:

~~~text
provider returns EmailProviderResult(FAILED)
-> normal domain outcome
-> DeliveryAttempt FAILED
-> CommunicationRecord FAILED
-> email.failed

provider violates protocol / missing configuration
-> exception
~~~

Concrete adapters normalize their supported provider/network failure modes into
EmailProviderResult where specified.

## 75. Send transaction

The Memory send workflow persists in one Unit of Work:

~~~text
CommunicationIntent
queued EmailDeliveryEvent
DeliveryAttempt
CommunicationRecord
sent/failed EmailDeliveryEvent
audit/events
Timeline projections
~~~

and then commits once.

## 76. Provider call occurs before commit

One important integration boundary remains:

~~~text
provider.send(...)
happens during the Unit of Work
before commit
~~~

Therefore the CRM's local persistence can be transactional, while the remote
provider call is still an external side effect.

Do not describe this as a distributed transaction.

## 77. Outbound idempotency key

crm.email.send accepts:

~~~text
idempotency_key
~~~

When a successfully committed Intent with that key already has a
CommunicationRecord, a retry returns the existing record before invoking the
provider again.

This prevents repeat provider submission **after a successful committed send**
for that key.

## 78. Email send idempotency differs from Lead Conversion

This is an important difference between chapters 13 and 14.

Lead Conversion stores:

~~~text
idempotency key
+
canonical request fingerprint
~~~

Email send V1 uses the idempotency key to find the existing committed Intent /
Record.

It does **not** compare a canonical fingerprint of the repeated email request.

Therefore the contract is:

~~~text
same committed email idempotency key
-> return existing CommunicationRecord
-> no second provider call
~~~

Applications should treat one idempotency key as the stable identity of one
logical outbound send.

## 79. Incomplete idempotent replay

If an Intent exists for an idempotency key but no CommunicationRecord can be
found:

~~~text
DuplicateError
code = communication.email.idempotency.incomplete
~~~

The facade does not silently resubmit an incomplete local state.

## 80. Repository-level idempotency uniqueness

MemoryCommunicationRepository also rejects two different Intents carrying the
same normalized stored idempotency key:

~~~text
DuplicateError
code = communication.intent.idempotency_key.duplicate
~~~

The repository protects the persistence contract even below the facade.

## 81. Idempotency is not a remote two-phase commit

If an external provider side effect occurs but local persistence never commits,
local replay protection alone cannot prove the remote outcome.

Provider-native idempotency support can further reduce that uncertainty.

EmailMessage forwards the Communication idempotency key to providers, and
concrete adapters may map it according to their capabilities.

## 82. Event payload privacy

Stable Communication events deliberately avoid message bodies and recipient
addresses in their emitted DomainEvent payloads.

The facade lifecycle payload contains context such as:

~~~text
delivery_status
provider
business_occurred_at
~~~

but not:

~~~text
recipient email address
text body
HTML body
~~~

This matters for privacy and audit/event propagation.

## 83. Timeline projection

Meaningful Communication lifecycle events project into Timeline as:

~~~text
TimelineEntryKind.COMMUNICATION
~~~

The Timeline event_type preserves:

~~~text
email.queued
email.sent
email.delivered
email.opened
email.clicked
email.bounced
email.failed
~~~

where applicable to the referenced CRM entities.

## 84. Timeline does not become the source of truth

Timeline is a read model.

The source remains:

~~~text
CommunicationRecord
+
EmailDeliveryEvent history
~~~

Timeline answers cross-domain customer-history questions.

Communication answers email-delivery questions.

## 85. Complete direct-send example

~~~python
from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.communication import (
    CommunicationAddress,
    CommunicationChannel,
    CommunicationContent,
    CommunicationRecipient,
    EmailDeliveryEventType,
    EmailDeliveryStatus,
    EmailProviderResult,
)
from pycrmkit.core.references import EntityReference
from pycrmkit.core.time import FixedClock

class AcceptingProvider:
    def send(self, message):
        return EmailProviderResult(
            provider="fake",
            status=EmailDeliveryStatus.ACCEPTED,
            provider_message_id="provider-001",
        )

clock = FixedClock(
    datetime(2026, 9, 28, 8, 0, tzinfo=UTC)
)

crm = CRM.memory(
    clock=clock,
    email_provider=AcceptingProvider(),
    email_sender=CommunicationAddress(
        CommunicationChannel.EMAIL,
        "sales@example.com",
    ),
).with_context(
    actor_id="seller-42",
    correlation_id="email-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

reference = EntityReference(
    "contact",
    contact.id,
)

record = crm.email.send(
    to=(
        CommunicationRecipient(
            CommunicationAddress(
                CommunicationChannel.EMAIL,
                "Ada@Example.com",
            ),
            display_name="Ada Lovelace",
            reference=reference,
        ),
    ),
    content=CommunicationContent(
        subject="  Enterprise   proposal ",
        text_body="Your proposal is ready.",
    ),
    idempotency_key="proposal-001",
)

assert record.subject == "Enterprise proposal"
assert record.delivery_status is EmailDeliveryEventType.SENT
assert record.external_id == "provider-001"
assert crm.email.for_contact(contact.id).items == (record,)
~~~

## 86. Record downstream callbacks

~~~python
clock.advance(timedelta(minutes=1))

delivered = crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-001",
    event_type="delivered",
    occurred_at=clock.now(),
    external_event_id="evt-delivered-001",
)

assert delivered.event_type is EmailDeliveryEventType.DELIVERED

clock.advance(timedelta(minutes=1))

opened = crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-001",
    event_type="opened",
    occurred_at=clock.now(),
    external_event_id="evt-opened-001",
)

assert opened.event_type is EmailDeliveryEventType.OPENED

current = crm.email.get(record.id)
assert current.delivery_status is EmailDeliveryEventType.OPENED
~~~

## 87. Callback replay example

~~~python
before = crm.email.delivery_history(
    record.id,
).total

replay = crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-001",
    event_type="opened",
    occurred_at=clock.now(),
    external_event_id="evt-opened-001",
)

after = crm.email.delivery_history(
    record.id,
).total

assert replay.id == opened.id
assert after == before
~~~

## 88. Delivery history example

~~~python
history = crm.email.delivery_history(
    record.id,
)

types = {
    item.event_type
    for item in history.items
}

assert {
    EmailDeliveryEventType.QUEUED,
    EmailDeliveryEventType.SENT,
    EmailDeliveryEventType.DELIVERED,
    EmailDeliveryEventType.OPENED,
} <= types
~~~

## 89. Timeline example

~~~python
from pycrmkit.timeline import TimelineEntryKind

timeline = crm.timeline.for_contact(
    contact.id,
    kind=TimelineEntryKind.COMMUNICATION,
)

event_types = {
    str(item.event_type)
    for item in timeline.items
}

assert {
    "email.queued",
    "email.sent",
    "email.delivered",
    "email.opened",
} <= event_types
~~~

## 90. Provider-neutral templates

EmailTemplate stores:

~~~text
name
subject_template?
text_template?
html_template?
~~~

At least one body template is required.

Example:

~~~python
from pycrmkit.communication import EmailTemplate

template = EmailTemplate(
    name="proposal_followup",
    subject_template="Hello {{ name }}",
    text_template="Your proposal is ready, {{ name }}.",
    html_template="<strong>Your proposal is ready, {{ name }}.</strong>",
)
~~~

The core Communication domain does not mandate Jinja2.

## 91. TemplateRenderer Protocol

The rendering seam is:

~~~python
class TemplateRenderer(Protocol):
    def render(
        self,
        template: EmailTemplate,
        context: Mapping[str, object],
    ) -> CommunicationContent:
        ...
~~~

Any renderer can satisfy the contract.

## 92. Sending a template

crm.email.send supports:

~~~python
record = crm.email.send(
    to=(recipient,),
    template=template,
    template_context={
        "name": "Ada",
    },
)
~~~

A configured TemplateRenderer converts the template into CommunicationContent
before the Unit of Work send workflow.

## 93. Missing renderer

Sending a template without a configured renderer raises:

~~~text
IntegrationError
code = communication.email.template.renderer_required
~~~

Direct CommunicationContent does not require a renderer.

## 94. Jinja2 renderer

PyCRMKit ships an optional Jinja2 renderer.

Install:

~~~text
pip install "pycrmkit[email]"
~~~

Then:

~~~python
from pycrmkit.providers.email.jinja2 import (
    Jinja2TemplateRenderer,
)
~~~

Its stable behavior includes:

- strict missing-variable failure;
- HTML autoescaping by default;
- subject rendering without HTML autoescaping;
- plain-text rendering without HTML autoescaping.

## 95. Jinja render failure

Missing required Jinja context is normalized as:

~~~text
IntegrationError
code = communication.email.template.render_failed
~~~

with the template name in error context.

## 96. SMTP adapter

The concrete stdlib adapter is:

~~~python
from pycrmkit.providers.email import (
    SMTPConfig,
    SMTPEmailProvider,
    SMTPSecurity,
)
~~~

Supported connection modes:

~~~text
plain
starttls
tls
~~~

SMTP is an adapter behind EmailProvider, not part of the Communication domain.

## 97. SMTP mapping

The SMTP adapter maps EmailMessage into MIME with:

~~~text
From
To
Subject?
Message-ID
X-PyCRMKit-Intent-ID
X-PyCRMKit-Idempotency-Key?
text / HTML / multipart alternative body
~~~

The generated RFC Message-ID becomes provider_message_id.

## 98. SMTP failure normalization

Supported SMTP/auth/network failures are mapped into:

~~~text
EmailProviderResult(
    status="failed",
    failure_code=...
)
~~~

This preserves the provider-neutral domain contract.

## 99. SMTP partial recipient refusal

SMTP may accept some recipients and reject others.

Stable adapter behavior:

~~~text
at least part accepted
-> status ACCEPTED
~~~

accepted/refused counts are recorded in provider metadata.

Per-recipient final delivery semantics are not inferred from SMTP submission
acceptance.

## 100. Resend adapter

Resend is optional:

~~~text
pip install "pycrmkit[resend]"
~~~

Provider:

~~~python
from pycrmkit.providers.email.resend import (
    ResendConfig,
    ResendEmailProvider,
)
~~~

The base pycrmkit installation does not require the Resend SDK.

## 101. Resend mapping

The adapter maps:

~~~text
sender          -> from
recipients      -> to
subject         -> subject
text_body       -> text
html_body       -> html
intent ID       -> X-PyCRMKit-Intent-ID
idempotency key -> Resend send options
~~~

Generic CRM references are not forwarded to the provider.

## 102. Resend result and failure normalization

A successful Resend response must contain an email ID, which becomes:

~~~text
provider_message_id
~~~

Provider errors are normalized into typed failure codes such as:

~~~text
resend.rate_limit_exceeded
resend.invalid_api_key
resend.http_client_error
resend.invalid_request
resend.invalid_response
~~~

Provider error message text is deliberately not persisted into metadata by this
adapter contract.

## 103. Stable crm.email facade

The frozen V1 public facade is:

~~~text
crm.email.send
crm.email.record_delivery_event
crm.email.get
crm.email.for_contact
crm.email.for_organization
crm.email.delivery_history
~~~

This is the application-facing Communication surface.

## 104. CommunicationRepository

The backend-neutral persistence contract contains operations for:

~~~text
Intent
├── get_intent
├── find_intent_by_idempotency_key
└── save_intent

DeliveryAttempt
├── get_attempt
├── find_attempt_by_provider_message_id
└── save_attempt

CommunicationRecord
├── get_record
├── find_record_by_intent
├── find_record_by_attempt
├── save_record
└── list_records_for_reference

EmailDeliveryEvent
├── find_delivery_event_by_external_id
├── append_delivery_event
└── list_delivery_events_for_intent
~~~

Repositories persist history; they do not choose transport providers.

## 105. Memory repository uniqueness

The Memory adapter protects:

~~~text
one stored Intent per idempotency key
one DeliveryAttempt per provider/provider_message_id
one CommunicationRecord per Intent
one CommunicationRecord per DeliveryAttempt
provider external event identity consistency
~~~

It also provides copy isolation for mutable entity state.

## 106. Public send test

A useful application test uses a fake provider:

~~~python
def test_send_email() -> None:
    provider = AcceptingProvider()

    crm = CRM.memory(
        email_provider=provider,
        email_sender=CommunicationAddress(
            CommunicationChannel.EMAIL,
            "sales@example.com",
        ),
    )

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )

    record = crm.email.send(
        to=(
            CommunicationRecipient(
                CommunicationAddress(
                    CommunicationChannel.EMAIL,
                    "ada@example.com",
                ),
                reference=EntityReference(
                    "contact",
                    contact.id,
                ),
            ),
        ),
        content=CommunicationContent(
            subject="Proposal",
            text_body="Ready.",
        ),
        idempotency_key="proposal-001",
    )

    assert record.delivery_status is EmailDeliveryEventType.SENT
    assert len(provider.messages) == 1
~~~

No live SMTP or Resend account is needed for domain/application tests.

## 107. Idempotent send test

~~~python
first = crm.email.send(
    to=(recipient,),
    content=content,
    idempotency_key="proposal-001",
)

retry = crm.email.send(
    to=(recipient,),
    content=content,
    idempotency_key="proposal-001",
)

assert retry.id == first.id
assert len(provider.messages) == 1
~~~

This proves no second provider submission after the committed first send.

## 108. Out-of-order callback test

~~~python
opened_at = NOW + timedelta(minutes=4)
late_delivered_at = NOW + timedelta(minutes=3)

crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-001",
    event_type="opened",
    occurred_at=opened_at,
    external_event_id="evt-opened",
)

crm.email.record_delivery_event(
    provider="fake",
    provider_message_id="provider-001",
    event_type="delivered",
    occurred_at=late_delivered_at,
    external_event_id="evt-late-delivered",
)

current = crm.email.get(record.id)

assert current.delivery_status is EmailDeliveryEventType.OPENED
~~~

Both events remain in history.

## Common mistakes

### Treating CommunicationIntent as delivery state

Intent lifecycle is DRAFT / QUEUED / CANCELLED. SENT and DELIVERED belong to
other layers.

### Treating ACCEPTED as mailbox delivery

ACCEPTED means provider transport acceptance only.

### Creating Activity(type="email") for every Communication

PyCRMKit's stable architecture keeps Communication as its own source domain and
projects it to Timeline.

### Putting CRM references into provider-specific logic

EmailMessage intentionally excludes generic CRM EntityReference values.

### Sending without configuring a provider

crm.email.send requires EmailProvider.

### Sending without a sender

Configure email_sender or pass sender explicitly.

### Supplying both content and template

Exactly one composition source is required.

### Using a template without TemplateRenderer

The facade raises communication.email.template.renderer_required.

### Expecting a provider FAILED result to raise

Normalized FAILED is persisted as delivery history and crm.email.send returns
the failed CommunicationRecord.

### Assuming email send idempotency compares request fingerprints

It does not. A committed matching idempotency key returns the existing record.

### Reusing one send idempotency key for unrelated content

Treat a send key as the identity of one logical outbound submission.

### Omitting external_event_id when the provider offers one

Without a provider event identity, callback replay cannot be deduplicated by
that mechanism.

### Expecting old callbacks to be discarded

They remain in append-only history; they simply do not regress current record
state when their occurred_at is older.

### Ordering callbacks by arrival time

Current delivery state uses business occurred_at, while updated_at can reflect
later ingestion recorded_at.

### Putting bodies or recipient addresses in emitted lifecycle payloads

The stable facade deliberately keeps them out of event payloads.

### Treating provider calls and local persistence as one distributed transaction

Provider.send is an external side effect invoked before local commit.

### Testing with live providers in ordinary CI

Use deterministic fake EmailProvider implementations for application tests.

## What you learned

You can now explain and use:

- Communication as its own bounded context;
- CommunicationChannel and CommunicationDirection;
- CommunicationAddress normalization;
- CommunicationRecipient and CRM references;
- CommunicationContent;
- CommunicationIntent and its DRAFT/QUEUED/CANCELLED lifecycle;
- EmailMessage as provider DTO;
- EmailProvider Protocol;
- EmailProviderResult;
- ACCEPTED vs downstream delivery;
- EmailDeliveryService;
- DeliveryAttempt and its PENDING/ACCEPTED/FAILED lifecycle;
- CommunicationRecord as authoritative CRM communication history;
- direct-content email sending;
- Contact and Organization communication history;
- normalized email lifecycle names;
- EmailDeliveryEvent append-only history;
- occurred_at vs recorded_at;
- provider-message callback correlation;
- external-event callback idempotency;
- conflicting callback detection;
- out-of-order callback state protection;
- outbound-send idempotency and its non-fingerprint boundary;
- provider failure as a normalized domain outcome;
- event payload privacy;
- Communication Timeline projection;
- provider-neutral EmailTemplate and TemplateRenderer;
- optional Jinja2 rendering;
- SMTP as a concrete EmailProvider adapter;
- Resend as an optional EmailProvider adapter;
- CommunicationRepository and Memory adapter guarantees;
- the stable crm.email public facade.

## LEVEL 4 in progress

You have now entered the Communication & Automation layer.

The first chapter establishes the domain event producers that automation will
consume:

~~~text
Email send
   |
   +--> email.queued
   +--> email.sent / email.failed
   |
Provider callbacks
   |
   +--> email.delivered
   +--> email.opened
   +--> email.clicked
   +--> email.bounced
   +--> email.failed
~~~

The next chapters explain the generic event infrastructure and durable webhook
delivery built on top of these domain events.

## Next

The next chapter is **15 - Domain Events**.

You have already consumed DomainEvent values throughout the learning path.

Now we will open the eventing layer itself:

~~~text
Domain mutation
      |
      v
DomainEvent
      |
      +--> registry
      +--> serialization
      +--> correlation / causation
      +--> in-process subscribers
      |
      v
Webhook delivery in chapter 16
~~~

The next learning question is:

> How does PyCRMKit turn domain changes into a stable, serializable and causally
> linked event stream without coupling business domains to consumers?
