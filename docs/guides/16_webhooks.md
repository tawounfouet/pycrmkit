# Webhooks

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter closes **LEVEL 4 - Communication & Automation**.

Chapter 15 established the internal event foundation:

~~~text
Domain mutation
      |
      v
DomainEvent
      |
      +--> EventRegistry
      +--> EventSerializer
      +--> InProcessEventBus
~~~

Webhooks take selected committed DomainEvents across the process boundary.

The central question is:

~~~text
How does PyCRMKit deliver selected domain events to external HTTP systems
with deterministic payloads, signatures, retries, idempotency and history?
~~~

## What you will build

You will:

- register persistent webhook subscriptions;
- understand exact EventType filtering;
- validate and normalize webhook URLs;
- manage signing secrets safely;
- rotate secrets without leaking them to audit;
- understand automatic post-commit webhook delivery;
- disable auto-delivery and dispatch manually;
- serialize canonical event JSON;
- sign requests with HMAC-SHA256;
- verify signatures and optional timestamp freshness;
- understand the WebhookTransport protocol;
- understand StdlibWebhookTransport security defaults;
- distinguish retryable and terminal HTTP outcomes;
- use deterministic exponential backoff;
- inspect WebhookDelivery state;
- inspect append-only WebhookDeliveryAttempt history;
- understand idempotency by subscription/event pair;
- understand replay behavior;
- understand disabled-subscription behavior;
- understand dead-letter semantics;
- query deliveries and attempts;
- understand the Memory adapter contract;
- understand the stable production boundary of the webhook system.

The mental model is:

~~~text
Committed DomainEvent
        |
        v
WebhookEventBridge
        |
        v
matching enabled subscription
        |
        v
EventSerializer
        |
        v
canonical JSON
        |
        v
HMAC signature
        |
        v
WebhookTransport
        |
        +--> 2xx
        |      |
        |      v
        |   SUCCEEDED
        |
        +--> retryable failure
        |      |
        |      v
        |   RETRY_SCHEDULED
        |      |
        |      v
        |   retry_due()
        |
        +--> terminal / exhausted
               |
               v
           DEAD_LETTER
~~~

## 1. Why Webhooks exist

In-process subscribers are useful only inside one Python process.

External systems need a transport boundary.

Examples:

~~~text
CRM
  |
  +--> billing platform
  +--> analytics service
  +--> marketing automation
  +--> ERP
  +--> integration gateway
~~~

Webhooks provide an HTTP delivery mechanism without making Contacts, Leads,
Opportunities or other business domains perform network calls directly.

## 2. Webhooks consume DomainEvents

Webhook delivery starts from a DomainEvent.

It does not define a second business-event format.

The delivery body is canonical EventSerializer JSON from chapter 15.

Therefore:

~~~text
DomainEvent
is the business occurrence

WebhookDelivery
is the delivery state for one external subscription
~~~

## 3. Stable public facade

The stable V1 Webhooks facade exposes:

~~~text
crm.webhooks.register
crm.webhooks.rotate_secret
crm.webhooks.disable
crm.webhooks.list

crm.webhooks.deliver
crm.webhooks.retry_due
crm.webhooks.deliveries
crm.webhooks.attempts
~~~

These APIs cover registration, delivery execution and delivery history.

## 4. WebhookSubscription

A subscription stores:

~~~text
id
created_at
updated_at
url
event_types
signing_secret
disabled_at
~~~

Typed identity:

~~~text
WebhookSubscriptionId
~~~

The subscription is persistent application state.

## 5. Registration example

~~~python
subscription = crm.webhooks.register(
    url="https://hooks.example.com/crm",
    events=(
        "contact.created",
        "opportunity.won",
    ),
    signing_secret="0123456789abcdef0123456789abcdef",
)
~~~

The returned subscription is enabled.

~~~python
assert subscription.enabled is True
~~~

## 6. At least one event type is required

A subscription with no event types is invalid.

Stable error:

~~~text
ValidationError
code = webhook.events.required
~~~

## 7. Event types are normalized

The subscription converts each event name through EventType.parse.

Duplicates are removed.

The resulting tuple is sorted by event name.

Example:

~~~text
input:
opportunity.won
contact.created
contact.created

stored:
contact.created
opportunity.won
~~~

## 8. Registration requires a known public event type

WebhookSubscriptionService.register validates each requested EventType against
the configured EventRegistry.

The service uses registry.latest(event_type).

Therefore the EventType must exist in the registry.

Unknown event type registration raises registry not-found semantics.

## 9. Subscription filters by EventType, not version

A subscription stores EventType values only.

It does not store schema_version.

That means the subscription conceptually says:

~~~text
I want contact.created
~~~

not:

~~~text
I want only contact.created v1
~~~

However, the actual DomainEvent is still validated against the EventRegistry
before delivery.

So an unsupported schema version is rejected before dispatch.

## 10. Custom events

Applications may inject a custom EventRegistry into CRM.

If a custom event type is registered there, a webhook subscription may register
for it.

Without registry support, the subscription service rejects the event type.

## 11. URL normalization

Webhook registration accepts HTTP or HTTPS URLs.

Normalization:

~~~text
trim
lowercase scheme
lowercase / IDNA-normalize host
preserve explicit port
default empty path to /
preserve query
remove fragment by rejection
~~~

Example:

~~~python
from pycrmkit.webhooks import normalize_webhook_url

assert (
    normalize_webhook_url(
        " HTTPS://Hooks.Example.COM "
    )
    == "https://hooks.example.com/"
)
~~~

## 12. URL scheme

Allowed:

~~~text
http
https
~~~

Not allowed:

~~~text
ftp
file
mailto
other schemes
~~~

Invalid scheme or missing host raises:

~~~text
webhook.url.invalid
~~~

## 13. Embedded credentials are forbidden

This is rejected:

~~~text
https://user:password@example.com/hook
~~~

Stable error:

~~~text
webhook.url.credentials_forbidden
~~~

## 14. URL fragments are forbidden

This is rejected:

~~~text
https://example.com/hook#fragment
~~~

Stable error:

~~~text
webhook.url.fragment_forbidden
~~~

## 15. Whitespace and header-injection forms are rejected

URLs containing whitespace or newline/header-injection patterns fail validation.

The registration layer therefore rejects many malformed request-target forms
before any network operation.

## 16. URL length

Webhook URL maximum length is 2048 characters.

Overlong values are invalid.

## 17. Registration performs no network I/O

This is an important security boundary.

crm.webhooks.register validates syntax and persists the subscription.

It does not:

- resolve DNS;
- connect to the endpoint;
- check TLS;
- send a verification request.

Network safety checks belong to the transport layer at delivery time.

## 18. Signing secret

Each subscription has a signing secret.

If the caller supplies one, it is normalized and validated.

If the caller omits it, PyCRMKit generates a high-entropy URL-safe secret.

## 19. Secret length

Webhook signing secret must encode to between:

~~~text
16 bytes
and
512 bytes
~~~

Invalid values raise:

~~~text
webhook.signing.secret.invalid
~~~

## 20. Generated secret

PyCRMKit uses a secure random URL-safe token generator for automatic secret
creation.

Applications must still distribute and store the secret through their own
secure operational process.

## 21. Secret is persisted because delivery needs it

PyCRMKit must access the secret later to sign requests.

Therefore supported persistence adapters store the configured signing secret as
application data.

PyCRMKit does not claim transparent encryption-at-rest for this field.

## 22. Secret-safe representations

Secret-bearing fields are excluded from ordinary representation paths where
qualified by the security model.

WebhookSubscription.signing_secret is repr-hidden.

WebhookRequest URL/body/headers are also repr-hidden.

This reduces accidental diagnostic leakage.

## 23. Registration audit

crm.webhooks.register records:

~~~text
webhook.subscription.registered
~~~

Audit changes store field names:

~~~text
url
event_types
~~~

not the signing secret value.

## 24. Rotate a signing secret

Stable V1 exposes:

~~~python
rotated = crm.webhooks.rotate_secret(
    subscription.id,
    signing_secret="fedcba9876543210fedcba9876543210",
)
~~~

The subscription persists the new secret.

## 25. Automatic secret rotation

If signing_secret is omitted during rotate_secret, PyCRMKit generates a fresh
secret automatically.

## 26. Idempotent rotation

If the supplied new secret is equal to the active secret:

~~~text
no state change
no new audit entry
~~~

The comparison uses constant-time hmac.compare_digest.

## 27. Rotation timestamp

The rotation timestamp cannot be before subscription creation.

Invalid chronology raises:

~~~text
webhook.signing.rotation_time.invalid
~~~

## 28. Rotation audit privacy

A real secret rotation records:

~~~text
webhook.subscription.secret_rotated
~~~

with changes indicating only:

~~~text
signing_secret
~~~

The old and new secret values are not copied into audit changes.

## 29. Disable a subscription

~~~python
disabled = crm.webhooks.disable(
    subscription.id,
)

assert disabled.enabled is False
~~~

Disabling is a lifecycle action rather than hard deletion.

## 30. Disable is idempotent

Calling disable twice leaves the same disabled subscription.

The second call does not create another disable audit mutation.

## 31. Disabled subscription matching

A disabled subscription does not match new events.

WebhookSubscription.matches requires:

~~~text
enabled
AND
event type present
~~~

## 32. Disable chronology

disabled_at cannot be earlier than created_at.

Invalid chronology raises:

~~~text
webhook.disabled_at.invalid
~~~

## 33. List subscriptions

~~~python
page = crm.webhooks.list(
    enabled=True,
    event_type="contact.created",
)
~~~

Available filters:

~~~text
enabled
event_type
~~~

plus standard OffsetPageRequest pagination.

## 34. Subscription ordering

The Memory repository orders subscriptions by:

~~~text
created_at ASC
id ASC
~~~

This is deterministic.

## 35. Subscription repository contract

WebhookSubscriptionRepository exposes:

~~~text
get
find
save
search
~~~

The repository persists subscription state but performs no transport.

## 36. Automatic delivery

CRM.memory enables webhook auto-delivery by default.

~~~python
crm = CRM.memory(
    webhook_transport=transport,
)
~~~

When a matching subscription exists:

~~~python
crm.contacts.create(
    display_name="Ada",
)
~~~

can automatically produce:

~~~text
commit Contact
      |
      v
publish contact.created
      |
      v
WebhookEventBridge
      |
      v
crm.webhooks.deliver(event)
~~~

## 37. Auto delivery is post-commit

WebhookEventBridge is installed on the same InProcessEventBus used by the CRM.

The source Memory Unit of Work commits and releases its transaction before the
bus invokes the bridge.

Therefore the webhook delivery transaction is separate from the source mutation
transaction.

## 38. Webhook delivery failure cannot roll back source state

A webhook transport failure occurs after the source domain commit in automatic
delivery.

Therefore:

~~~text
Contact committed
        |
        v
Webhook failure
~~~

does not roll back the Contact.

The delivery engine instead records retry/dead-letter state.

## 39. Disable auto-delivery

~~~python
crm = CRM.memory(
    webhook_transport=transport,
    webhook_auto_delivery=False,
)
~~~

Committed events still publish on crm.events.

But they are not automatically sent to webhook subscriptions.

## 40. Manual delivery remains available

With or without automatic bridging:

~~~python
deliveries = crm.webhooks.deliver(
    event,
)
~~~

Manual delivery uses the same delivery engine and idempotency boundary.

## 41. Contextual CRM views do not duplicate the bridge

crm.with_context(...) and crm.with_event(...) share the same bridge instance.

Creating lightweight CRM views does not install duplicate webhook subscribers.

This prevents duplicate automatic dispatch.

## 42. WebhookEventBridge

The bridge subscribes once to each EventType present in the configured
EventRegistry.

Its install operation is idempotent.

Its uninstall operation removes only its own subscriptions.

Other event handlers remain registered.

## 43. Bridge validates exact event contract

When a registered EventType is observed, WebhookEventBridge validates the full
DomainEvent against EventRegistry.

This checks:

~~~text
event.type
+
event.schema_version
~~~

before invoking delivery.

## 44. Dispatch matches active subscriptions

WebhookDeliveryEngine.dispatch first validates the event contract.

It then searches all enabled subscriptions for the event type.

Only matching active subscriptions get deliveries.

## 45. Pagination inside dispatch

The engine scans matching subscriptions in pages of up to 200.

It continues until no next page remains.

Dispatch therefore supports more subscriptions than a single repository page.

## 46. One event may create multiple deliveries

If three enabled subscriptions all listen to contact.created:

~~~text
one DomainEvent
        |
        +--> delivery A
        +--> delivery B
        +--> delivery C
~~~

Each subscription gets its own delivery state and signing secret.

## 47. WebhookDelivery identity

One delivery is uniquely tied to:

~~~text
subscription_id
event_id
~~~

This is the stable delivery idempotency boundary.

## 48. WebhookDelivery fields

WebhookDelivery stores:

~~~text
id
subscription_id
event_id
event_type
payload_json
idempotency_key
state
attempt_count
next_attempt_at
last_attempt_at
completed_at
last_status_code
last_error_code
created_at
updated_at
~~~

Typed identity:

~~~text
WebhookDeliveryId
~~~

## 49. Canonical payload is retained

payload_json is the canonical EventSerializer representation of the original
DomainEvent.

The delivery stores it so retries can occur after the original event callback
has returned.

## 50. Why payload_json is retained

retry_due() works from persisted WebhookDelivery state.

It does not need the original DomainEvent object to still exist in memory.

That is the important bridge between:

~~~text
ephemeral in-process event
and
persistent retry state
~~~

## 51. Payload conflict protection

If a delivery already exists for the same:

~~~text
subscription_id
event_id
~~~

but the newly serialized event payload differs, dispatch raises:

~~~text
DuplicateError
code = webhook.delivery.event_conflict
~~~

An EventId cannot silently represent two different webhook payloads.

## 52. Deterministic idempotency key

The outbound idempotency key is derived from:

~~~text
subscription_id
+
event_id
~~~

using SHA-256 and the prefix:

~~~text
whd_
~~~

Retries for the same delivery reuse exactly the same key.

## 53. Terminal replay

If a delivery is already:

~~~text
SUCCEEDED
or
DEAD_LETTER
~~~

replaying the same event returns the existing delivery.

No new HTTP request is sent.

## 54. Scheduled replay before due time

If a delivery is RETRY_SCHEDULED but next_attempt_at is still in the future,
manual dispatch returns the existing delivery without sending early.

## 55. Webhook delivery states

Stable states:

~~~text
PENDING
RETRY_SCHEDULED
SUCCEEDED
DEAD_LETTER
~~~

State values:

~~~text
pending
retry_scheduled
succeeded
dead_letter
~~~

## 56. PENDING

A new WebhookDelivery starts PENDING.

The engine persists it before attempting transport.

Then the first attempt normally moves it immediately to:

~~~text
SUCCEEDED
RETRY_SCHEDULED
DEAD_LETTER
~~~

## 57. SUCCEEDED

Any HTTP 2xx response means delivery success.

Examples:

~~~text
200
201
202
204
299
~~~

The delivery becomes SUCCEEDED.

completed_at is set.

next_attempt_at becomes None.

## 58. Retryable HTTP statuses

Default retryable statuses are:

~~~text
408
425
429
500-599
~~~

Examples:

~~~text
408 Request Timeout
425 Too Early
429 Too Many Requests
503 Service Unavailable
~~~

## 59. Non-retryable HTTP statuses

Other non-2xx responses are terminal for that delivery.

Examples:

~~~text
301
400
401
404
422
~~~

They enter DEAD_LETTER immediately.

## 60. Redirects are not followed

StdlibWebhookTransport uses a redirect handler that refuses redirect following.

A 3xx HTTP response is returned to the delivery engine as status metadata.

Because ordinary 3xx statuses are not retryable by default, they become
DEAD_LETTER.

## 61. Transport failures

WebhookTransportError represents normalized transport failures.

The delivery engine treats transport errors as retryable.

Built-in examples:

~~~text
webhook.transport.timeout
webhook.transport.network_error
webhook.transport.dns_error
webhook.transport.destination_forbidden
~~~

## 62. Retry policy defaults

WebhookRetryPolicy defaults:

~~~text
max_attempts = 5
base_delay   = 10 seconds
max_delay    = 10 minutes
~~~

## 63. Exponential backoff

Delay after a failed attempt:

~~~text
attempt 1 -> 10 seconds
attempt 2 -> 20 seconds
attempt 3 -> 40 seconds
attempt 4 -> 80 seconds
...
capped at 10 minutes
~~~

Formula:

~~~text
base_delay * 2^(attempt_number - 1)
~~~

then capped by max_delay.

## 64. Retry policy validation

Invalid examples:

~~~text
max_attempts <= 0
base_delay <= 0
max_delay < base_delay
~~~

raise typed ValidationError values.

## 65. Retry scheduling

On retryable failure before max_attempts:

~~~text
state = RETRY_SCHEDULED
next_attempt_at = failed_at + delay
completed_at = None
~~~

## 66. retry_due()

~~~python
retried = crm.webhooks.retry_due()
~~~

The engine finds all deliveries whose:

~~~text
state = RETRY_SCHEDULED
next_attempt_at <= now
~~~

and processes them.

## 67. No early retry

If no delivery is due:

~~~python
assert crm.webhooks.retry_due() == ()
~~~

The engine does not send before next_attempt_at.

## 68. Maximum attempts

When the current failure reaches max_attempts:

~~~text
DEAD_LETTER
~~~

even if the underlying failure would otherwise be retryable.

## 69. Dead-letter state

DEAD_LETTER is terminal for the current delivery.

The engine does not automatically resubmit a dead-letter delivery.

Replaying the same event returns the existing terminal state.

## 70. Disabled subscription during retry

A delivery may have been scheduled while a subscription was enabled.

If the subscription is disabled before the retry attempt, the next due
processing records:

~~~text
DEAD_LETTER
error_code = webhook.subscription_disabled
~~~

without calling the transport.

## 71. WebhookDeliveryAttempt

Every actual processing outcome is appended as an immutable attempt record.

Fields:

~~~text
delivery_id
attempt_number
attempted_at
outcome
status_code
error_code
next_attempt_at
~~~

## 72. Attempt outcomes

Stable values:

~~~text
succeeded
retry_scheduled
dead_letter
~~~

These mirror the result of that specific attempt.

## 73. Append-only attempt history

Each attempt number is retained.

Example:

~~~text
attempt 1:
503
retry_scheduled

attempt 2:
204
succeeded
~~~

The first attempt remains available after success.

## 74. Attempt numbering

attempt_number must be a positive integer.

The engine uses:

~~~text
delivery.attempt_count + 1
~~~

for the next attempt.

## 75. Attempt ordering

The Memory repository returns attempts ordered by:

~~~text
attempt_number ASC
~~~

## 76. Duplicate attempt protection

The Memory repository keys attempts by:

~~~text
(delivery_id, attempt_number)
~~~

Appending the exact same attempt is idempotent.

Appending conflicting data for the same number raises:

~~~text
webhook.delivery.attempt.duplicate
~~~

## 77. Delivery attempt_count

WebhookDelivery increments attempt_count for every:

~~~text
success
retry schedule
dead-letter result
~~~

It reflects completed processing attempts.

## 78. Delivery search

~~~python
page = crm.webhooks.deliveries(
    subscription_id=subscription.id,
    state="retry_scheduled",
)
~~~

Filters:

~~~text
subscription_id
event_id
state
~~~

## 79. Delivery ordering

Memory delivery search orders by:

~~~text
created_at ASC
id ASC
~~~

## 80. Due-delivery ordering

Due deliveries are ordered by:

~~~text
next_attempt_at ASC
id ASC
~~~

## 81. Attempt history query

~~~python
attempts = crm.webhooks.attempts(
    delivery.id,
)
~~~

The delivery must exist.

Missing delivery uses:

~~~text
webhook.delivery.not_found
~~~

## 82. Canonical HTTP body

The request body is:

~~~text
EventSerializer.dumps(event).encode("utf-8")
~~~

The exact canonical JSON from chapter 15 is what gets signed and transmitted.

## 83. Webhook request headers

Stable request headers include:

~~~text
Content-Type: application/json
User-Agent: PyCRMKit-Webhooks/0.5
X-PyCRMKit-Delivery-ID
X-PyCRMKit-Event-ID
X-PyCRMKit-Event-Type
X-PyCRMKit-Idempotency-Key
X-PyCRMKit-Timestamp
X-PyCRMKit-Signature
~~~

## 84. Timestamp header

X-PyCRMKit-Timestamp is:

~~~text
int(clock.now().timestamp())
~~~

The same integer timestamp participates in the HMAC signature.

## 85. HMAC signature

Stable signing contract:

~~~text
v1=HMAC_SHA256(
    secret,
    "<unix_timestamp>.<payload_bytes>"
)
~~~

The timestamp and exact body bytes are both authenticated.

## 86. sign_webhook_payload()

~~~python
signature = sign_webhook_payload(
    secret,
    timestamp,
    payload,
)
~~~

The return value starts with:

~~~text
v1=
~~~

## 87. Constant-time verification

verify_webhook_signature uses:

~~~text
hmac.compare_digest
~~~

for signature comparison.

## 88. Tamper protection

Changing any of these invalidates verification:

~~~text
secret
timestamp
payload bytes
signature
~~~

## 89. Unknown signature prefix

A signature beginning with another version prefix such as:

~~~text
v2=
~~~

is rejected by the V1 verifier.

## 90. Optional replay-age protection

The four-argument verification form checks integrity only.

For internet-facing receivers, V1 supports:

~~~python
verify_webhook_signature(
    secret,
    timestamp,
    payload,
    signature,
    current_timestamp=now,
    tolerance_seconds=300,
)
~~~

## 91. Freshness window

With tolerance 300:

~~~text
difference <= 300 seconds
-> accepted

difference > 300 seconds
-> rejected
~~~

even if the HMAC is otherwise valid.

## 92. Freshness validation parameters

Invalid current_timestamp or negative tolerance_seconds raise typed validation
errors.

## 93. Receiver-side verification sequence

A receiver should conceptually:

~~~text
read raw request body bytes
read X-PyCRMKit-Timestamp
read X-PyCRMKit-Signature
        |
        v
verify signature
        |
        v
optionally enforce freshness
        |
        v
parse JSON
        |
        v
use X-PyCRMKit-Idempotency-Key
for receiver-side deduplication
~~~

The raw bytes matter because the signature covers exact payload bytes.

## 94. WebhookTransport

The transport abstraction is:

~~~python
class WebhookTransport(Protocol):
    def send(
        self,
        request: WebhookRequest,
    ) -> WebhookResponse:
        ...
~~~

The delivery engine depends on this protocol, not on urllib directly.

## 95. Custom transport

Applications can supply their own transport:

~~~python
crm = CRM.memory(
    webhook_transport=my_transport,
)
~~~

This is ideal for:

~~~text
tests
custom HTTP stacks
network gateways
enterprise egress integrations
~~~

## 96. WebhookRequest

WebhookRequest contains:

~~~text
url
body
headers
timeout_seconds
~~~

Validation ensures:

~~~text
normalized webhook URL
body is bytes
timeout_seconds > 0
~~~

## 97. WebhookResponse

WebhookResponse retains only:

~~~text
status_code
headers
~~~

The status must be an integer from 100 through 599.

## 98. Response body is not part of WebhookResponse

The stable delivery engine does not persist arbitrary webhook response bodies.

This reduces privacy and secret leakage risk.

## 99. Raw exception messages are not persisted

Delivery state records normalized error codes.

It does not persist arbitrary exception messages from network failures.

## 100. StdlibWebhookTransport

The built-in transport uses Python standard library HTTP facilities.

It is synchronous.

It POSTs:

~~~text
request.body
with
request.headers
to
request.url
~~~

## 101. Public-destination policy

By default:

~~~text
allow_private_networks = False
~~~

The transport validates the target host before sending.

## 102. IP literal validation

If the hostname is already an IP address, the transport checks whether it is
globally routable.

Non-public addresses are rejected.

## 103. DNS validation

For hostnames, the transport resolves addresses with socket.getaddrinfo.

All resolved addresses must be public/global.

If any resolved address is non-public, delivery is rejected.

## 104. Loopback is blocked by default

Example:

~~~text
http://127.0.0.1:9999/hook
~~~

fails with:

~~~text
webhook.transport.destination_forbidden
~~~

before an HTTP request is performed.

## 105. Private-network opt-in

Trusted/local environments can use:

~~~python
transport = StdlibWebhookTransport(
    allow_private_networks=True,
)
~~~

This is an explicit security relaxation.

## 106. DNS failure

DNS resolution failure becomes:

~~~text
WebhookTransportError
code = webhook.transport.dns_error
~~~

## 107. Timeout

Timeout becomes:

~~~text
webhook.transport.timeout
~~~

and is retryable by the delivery engine.

## 108. Network errors

Other normalized network failures use:

~~~text
webhook.transport.network_error
~~~

and are retryable.

## 109. SSRF boundary

The transport checks reduce common SSRF exposure.

They are not presented as a complete network-isolation guarantee.

Production deployments should still use appropriate egress/network controls.

## 110. First success example

~~~python
transport = SequenceTransport(
    [
        WebhookResponse(204),
    ]
)

crm = CRM.memory(
    webhook_transport=transport,
)

subscription = crm.webhooks.register(
    url="https://hooks.example.com/crm",
    events=("contact.created",),
    signing_secret=SECRET,
)

captured = []
crm.events.subscribe(
    "contact.created",
    captured.append,
)

crm.contacts.create(
    display_name="Ada",
)

event = captured[0]

history = crm.webhooks.deliveries(
    event_id=event.id,
)

delivery = history.items[0]

assert delivery.subscription_id == subscription.id
assert delivery.state is WebhookDeliveryState.SUCCEEDED
assert delivery.attempt_count == 1
assert len(transport.requests) == 1
~~~

## 111. Retry example

Suppose the first request returns 503.

~~~text
attempt 1
503
        |
        v
RETRY_SCHEDULED
next_attempt_at = now + 10 seconds
~~~

Before the time is due:

~~~python
assert crm.webhooks.retry_due() == ()
~~~

After advancing the clock:

~~~text
attempt 2
204
        |
        v
SUCCEEDED
~~~

## 112. Same idempotency key across retries

The first and second request contain the same:

~~~text
X-PyCRMKit-Idempotency-Key
~~~

because both attempts belong to one WebhookDelivery.

## 113. Manual replay after success

~~~python
replay = crm.webhooks.deliver(
    event,
)

assert replay[0].id == delivery.id
~~~

No second HTTP request is sent for the terminal successful delivery.

## 114. Non-retryable 400 example

If the endpoint returns 400:

~~~text
attempt 1
        |
        v
DEAD_LETTER

last_error_code = webhook.http.400
~~~

No retry is scheduled.

## 115. Retry exhaustion example

With max_attempts=2:

~~~text
attempt 1 timeout
-> retry scheduled

attempt 2 timeout
-> dead letter
~~~

The final last_error_code remains the normalized transport error.

## 116. Attempt history example

~~~python
attempts = crm.webhooks.attempts(
    delivery.id,
)

assert [
    attempt.outcome.value
    for attempt in attempts.items
] == [
    "retry_scheduled",
    "succeeded",
]
~~~

## 117. Signature verification example

~~~python
request = transport.requests[0]

verified = verify_webhook_signature(
    subscription.signing_secret,
    int(
        request.headers[
            "X-PyCRMKit-Timestamp"
        ]
    ),
    request.body,
    request.headers[
        "X-PyCRMKit-Signature"
    ],
)

assert verified is True
~~~

## 118. Auto-delivery disabled example

~~~python
crm = CRM.memory(
    webhook_transport=transport,
    webhook_auto_delivery=False,
)

crm.webhooks.register(
    url="https://hooks.example.com/manual",
    events=("contact.created",),
    signing_secret=SECRET,
)

events = []
crm.events.subscribe(
    "contact.created",
    events.append,
)

crm.contacts.create(
    display_name="Manual",
)

assert transport.requests == []

crm.webhooks.deliver(
    events[0],
)

assert len(transport.requests) == 1
~~~

## 119. Subscription secret rotation example

~~~python
subscription = crm.webhooks.register(
    url="https://hooks.example.com/security",
    events=("contact.created",),
    signing_secret=OLD_SECRET,
)

rotated = crm.webhooks.rotate_secret(
    subscription.id,
    signing_secret=NEW_SECRET,
)

assert rotated.signing_secret == NEW_SECRET
~~~

Requests after rotation are signed with the new secret.

## 120. Old signatures fail after rotation

A receiver configured with the newly rotated secret will no longer accept a
signature generated with the old secret.

Secret rollout coordination remains an application/operator responsibility.

## 121. Registration audit and rotation audit

The stable actions are:

~~~text
webhook.subscription.registered
webhook.subscription.secret_rotated
webhook.subscription.disabled
~~~

Secret values are not stored in audit changes.

## 122. Delivery state is not an audit event

WebhookDelivery and WebhookDeliveryAttempt are dedicated delivery persistence
objects.

They are not merely audit entries.

Their job is operational reliability state.

## 123. Delivery persistence contract

WebhookDeliveryRepository exposes:

~~~text
get
find
find_by_subscription_event
save
search
list_due
append_attempt
list_attempts
~~~

This contract supports persistent retry logic independently of the transport.

## 124. Memory copy isolation

Memory webhook repositories deepcopy saved and returned entities.

Mutating a retrieved entity does not silently mutate stored state unless it is
explicitly saved through the repository/UoW.

## 125. Repository uniqueness

The Memory delivery repository enforces one WebhookDelivery per:

~~~text
subscription_id
event_id
~~~

A conflicting second delivery object for the same pair raises:

~~~text
webhook.delivery.duplicate
~~~

## 126. Stable transaction model

Automatic path:

~~~text
source CRM UoW
    |
    v
commit domain state
    |
    v
publish DomainEvent
    |
    v
WebhookEventBridge
    |
    v
new webhook delivery UoW
    |
    v
transport + delivery state
    |
    v
commit webhook delivery state
~~~

The two Unit-of-Work boundaries are separate.

## 127. Transport side effect vs webhook state commit

Within explicit webhook delivery:

~~~text
create/persist PENDING delivery in working state
        |
        v
call external transport
        |
        v
record success/retry/dead-letter in working state
        |
        v
commit webhook UoW
~~~

This is not a distributed transaction with the remote endpoint.

## 128. Why receiver idempotency still matters

A remote endpoint may process a request but the sender may not observe the
response reliably.

Retries can therefore happen in real distributed systems.

PyCRMKit supplies:

~~~text
X-PyCRMKit-Idempotency-Key
~~~

so receivers can deduplicate their own side effects.

## 129. Sender idempotency and receiver idempotency

Sender side:

~~~text
(subscription_id, event_id)
-> one WebhookDelivery
~~~

Receiver side:

~~~text
X-PyCRMKit-Idempotency-Key
-> consumer chooses how to deduplicate
~~~

Both sides matter.

## 130. Webhook auto-delivery and events_enabled

Automatic webhook bridging depends on DomainEvents reaching the event bus.

If facade event publication is disabled through CRMConfig.events_enabled=False,
ordinary facade mutations do not produce bus events for the automatic bridge.

Manual crm.webhooks.deliver(event) remains conceptually separate if the caller
already has a valid DomainEvent.

## 131. Webhooks vs in-process subscribers

~~~text
crm.events subscriber
= synchronous Python callable

webhook subscriber
= persisted HTTP destination + event filter
~~~

They share DomainEvent inputs but have different reliability and transport
semantics.

## 132. Webhooks vs provider callbacks

Chapter 14 provider callbacks such as email.opened ingestion are inbound events
from an email provider.

Webhooks are outbound delivery of PyCRMKit DomainEvents to external consumers.

Do not confuse the two directions.

## 133. Webhooks vs outbox

Stable V1 Memory webhooks persist deliveries and retry history.

They do not claim a production-grade distributed outbox/worker coordination
model.

Durable cross-process claiming and distributed delivery coordination are outside
the Memory-focused webhook contract.

## 134. Webhooks vs message brokers

Webhook transport is HTTP push.

It is not:

~~~text
Kafka
RabbitMQ
SQS
stream offsets
consumer groups
~~~

Applications that need those semantics can build adapters around DomainEvents.

## 135. Security responsibilities

PyCRMKit provides:

~~~text
URL syntax validation
HMAC signing
timestamp freshness helper
redirect rejection
public-IP destination checks
safe error codes
secret-safe audit behavior
~~~

Applications/operators remain responsible for:

~~~text
authorization
secret distribution
database protection
network egress controls
receiver authentication policy
endpoint availability
incident monitoring
~~~

## Common mistakes

### Treating registration as an endpoint connectivity check

Registration performs no network I/O.

### Registering an unknown event type

The event must exist in the configured EventRegistry.

### Assuming subscription captures one schema version

It filters by EventType; actual events are exact-version validated before
delivery.

### Treating a 3xx as success

Only 2xx is success. Redirects are not followed.

### Retrying every 4xx

Default retry is only 408, 425, 429 and 5xx.

### Retrying before next_attempt_at

retry_due processes only due deliveries.

### Creating a new delivery on every retry

Retries belong to the same WebhookDelivery.

### Generating a new idempotency key for each attempt

All attempts reuse the delivery idempotency key.

### Treating DEAD_LETTER as automatically retrying forever

Dead-letter is terminal for that delivery.

### Assuming disabling a subscription cancels already-scheduled retry state silently

When a due retry is processed for a disabled subscription, the delivery moves
to dead-letter with webhook.subscription_disabled.

### Signing re-serialized receiver JSON

Signature verification must use the exact raw payload bytes received.

### Ignoring timestamp replay age on internet-facing receivers

Use current_timestamp and tolerance_seconds when freshness checks are required.

### Storing webhook response bodies in delivery history

The stable model stores safe status/error metadata, not arbitrary body content.

### Storing raw network exception messages

Use normalized error codes.

### Assuming private addresses are allowed by the default transport

StdlibWebhookTransport blocks non-public destinations unless explicitly opted
in.

### Treating the public-destination check as complete SSRF isolation

Production egress controls are still recommended.

### Assuming auto-delivery runs before the source commit

The bridge runs post-commit.

### Assuming webhook failure rolls back the source aggregate

The source transaction is already committed.

### Treating the webhook engine as a distributed two-phase commit

HTTP side effects and local delivery persistence are not one atomic distributed
transaction.

### Creating many crm.with_context views and expecting many bridges

Contextual views share the same bridge instance.

## Testing Webhooks

A high-value webhook test suite should separate:

Registration:

~~~text
URL normalization
event registry validation
secret generation/validation
disable
secret rotation
audit privacy
~~~

Signing:

~~~text
stable HMAC vector
payload tampering
timestamp tampering
freshness tolerance
unknown prefix
~~~

Transport:

~~~text
public destination
loopback/private blocking
redirect handling
timeout
network error
~~~

Delivery:

~~~text
2xx success
503 retry
400 dead-letter
timeout retry
retry exhaustion
same idempotency key
duplicate dispatch
attempt history
~~~

Integration:

~~~text
source mutation commits
event publishes
bridge matches subscription
webhook sends
retry_due succeeds
history remains inspectable
~~~

## What you learned

You can now explain and use:

- WebhookSubscription;
- WebhookSubscriptionId;
- URL normalization;
- event-type registration validation;
- exact EventType filtering;
- version validation at event dispatch;
- signing-secret generation and validation;
- secret-safe representations;
- secret rotation;
- webhook registration/rotation/disable audit;
- subscription lifecycle;
- subscription queries;
- WebhookEventBridge;
- auto-delivery;
- manual delivery;
- webhook_auto_delivery=False;
- one bridge shared by contextual CRM views;
- WebhookDelivery;
- WebhookDeliveryId;
- WebhookDeliveryState;
- persistent canonical payload_json;
- delivery identity by subscription/event pair;
- deterministic whd_ idempotency key;
- payload conflict detection;
- terminal replay behavior;
- WebhookDeliveryAttempt;
- append-only attempt history;
- WebhookRetryPolicy;
- retryable status codes;
- capped exponential backoff;
- retry_due;
- dead-letter behavior;
- disabled-subscription retry behavior;
- EventSerializer body reuse;
- HMAC-SHA256 request signing;
- signature freshness validation;
- WebhookTransport;
- WebhookRequest;
- WebhookResponse;
- StdlibWebhookTransport;
- redirect rejection;
- public-destination checks;
- private-network opt-in;
- normalized timeout/network/DNS errors;
- safe delivery logging;
- receiver-side idempotency;
- webhook repository contracts;
- Memory ordering and copy isolation;
- post-commit source/delivery transaction separation;
- the boundaries among Webhooks, EventBus, callbacks, outbox and message brokers.

## LEVEL 4 complete

You have now completed Communication & Automation:

~~~text
14 Email & Communications
15 Domain Events
16 Webhooks
~~~

The full chain is now:

~~~text
CRM mutation
    |
    v
DomainEvent
    |
    +--> in-process subscribers
    |
    v
WebhookEventBridge
    |
    v
matching subscription
    |
    v
canonical serialized event
    |
    v
signed HTTP request
    |
    v
success / retry / dead letter
~~~

## Next

The next chapter begins **LEVEL 5 - Data Operations**:

**17 - External Identities**

The next learning problem is:

> How does PyCRMKit associate CRM entities with identifiers from external
> systems without leaking provider-specific identity concerns into core
> Contacts and Organizations?
