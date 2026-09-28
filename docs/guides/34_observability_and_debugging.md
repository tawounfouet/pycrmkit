# Observability & Debugging

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 7 - Production Applications**.

Chapter 33 established how to test a PyCRMKit application. This chapter asks a different production question:

> Once the application is running, how do operators understand what happened when a CRM operation succeeds, fails, retries or produces an unexpected side effect?

The stable V1 building blocks are:

~~~text
CRMContext
├── actor_id
├── correlation_id
└── causation_id

DomainEvent
├── id
├── type
├── aggregate_type
├── aggregate_id
├── actor_id
├── correlation_id
└── causation_id

AuditEntry
├── action
├── entity_type
├── entity_id
├── actor_id
└── correlation_id

PyCRMKitError
├── code
├── message
└── privacy-safe public context

WebhookDelivery
├── state
├── attempt_count
├── next_attempt_at
├── last_status_code
└── last_error_code
~~~

These are not a complete observability platform.

The current stable PyCRMKit surface does not provide a framework-owned logger, metrics registry, tracing SDK or OpenTelemetry integration.

That boundary is intentional:

> PyCRMKit exposes stable correlation, event, audit, error and delivery metadata. The embedding application decides how to send that metadata to logs, traces, metrics and operational dashboards.

## What you will learn

You will learn to:

- distinguish framework observability primitives from an observability platform;
- use actor, correlation and causation IDs correctly;
- propagate correlation through HTTP and event-triggered work;
- build privacy-safe structured application logs;
- query Audit by correlation, actor and entity;
- use Domain Events as operational evidence without treating them as a durable log;
- understand Timeline versus Audit;
- debug stable PyCRMKit errors;
- use safe persistence diagnostics;
- inspect webhook delivery state and attempts;
- use provider failure codes and safe metadata;
- understand post-commit subscriber failures;
- design useful log fields;
- avoid logging whole CRM payloads;
- connect application logs/traces without coupling PyCRMKit to a vendor.

## 1. Observability is application-owned

PyCRMKit provides domain and integration metadata.

It does not decide:

~~~text
log format
log destination
metrics backend
trace exporter
sampling policy
alerting rules
dashboard layout
incident workflow
~~~

A production application can use Python logging, structured logging, an APM agent, OpenTelemetry or another platform.

PyCRMKit remains independent of those choices.

## 2. PyCRMKit does not configure global logging

The stable source does not install framework-wide log handlers or formatters.

Importing PyCRMKit does not choose:

~~~text
log level
JSON formatter
service name
environment
trace exporter
~~~

Those remain application decisions.

## 3. Start with correlation

Assign or accept a correlation identifier at the outer application boundary.

~~~text
HTTP request / job
      |
correlation_id
      |
      v
CRM.with_context(...)
      |
      v
Domain Events + Audit
~~~

FastAPI and DRF already bridge X-Actor-ID and X-Correlation-ID into CRMContext.

## 4. Correlation represents the broader operation

One operation may touch:

~~~text
Contact
Task
Timeline
Audit
Webhook
~~~

The correlation ID should identify the broader workflow, not only one aggregate.

## 5. actor_id identifies the initiating principal

Examples:

~~~text
user-123
support-agent-7
import-job
system
~~~

Use stable non-secret identifiers.

## 6. causation_id identifies the direct parent event

For child work:

~~~text
contact.created
      |
      v
task.created
~~~

the child can keep the same correlation and use the parent EventId as causation_id.

## 7. CRM.with_event preserves causal context

CRM.with_event derives:

~~~text
actor_id       = parent.actor_id
correlation_id = parent.correlation_id or str(parent.id)
causation_id   = parent.id
~~~

## 8. Correlation and causation are different

~~~text
correlation_id
= whole trace

causation_id
= direct parent event
~~~

This distinction makes event chains reconstructable.

## 9. Generate correlation at an outer boundary

Typical boundaries include:

~~~text
HTTP middleware
CLI command
scheduled job
message consumer
import batch
background worker
~~~

Avoid generating a new correlation ID at every internal call.

## 10. Keep correlation values non-sensitive

Do not put email addresses, access tokens, customer names, phone numbers, passwords or request bodies inside correlation_id.

Correlation identifiers are designed to appear in diagnostics.

## 11. Structured logs should use stable fields

A useful success log may contain:

~~~text
event = crm.command.completed
operation = task.complete
entity_type = task
entity_id = ...
actor_id = ...
correlation_id = ...
result = success
~~~

## 12. Failure logs should add error_code

~~~text
event = crm.command.failed
operation = contact.update
error_code = contact.archived
correlation_id = ...
result = failure
~~~

Stable error codes are better anchors than parsed exception prose.

## 13. Prefer IDs over whole objects

Prefer:

~~~text
contact_id = ...
task_id = ...
~~~

over logging a whole Contact or Task object.

CRM entities can contain PII and arbitrary metadata.

## 14. Avoid raw request-body logging by default

Requests can contain email, phone, postal address, metadata, external identifiers, message content and secrets.

Request logging must follow the application's privacy policy.

## 15. Use public-safe error serialization

PyCRMKitError.as_dict applies sensitive-key redaction.

FastAPI and DRF public error bridges use the same protection.

## 16. Raw error.context can still be sensitive

Do not assume direct logging of error.context is safe.

The public serializer is the privacy boundary.

## 17. Messages must also stay safe

Key-based redaction cannot sanitize arbitrary secret text embedded in a message.

Prefer stable error codes plus deliberately safe messages and context.

## 18. Audit is persistent operational history

Audit answers:

~~~text
what action happened?
which entity changed?
who initiated it?
when?
which correlation trace?
which safe field evidence?
~~~

## 19. Audit is queryable by entity

~~~python
crm.audit.for_entity(
    "contact",
    contact.id,
)
~~~

## 20. Audit is queryable by actor and correlation

~~~python
crm.audit.by_actor("support-agent-7")
crm.audit.by_correlation("request-abc")
~~~

Correlation lookup is especially useful during incident investigation.


## 21. Audit is not a debug dump

AuditEntry.changes is explicit, minimized evidence.

It should not become storage for:

~~~text
stack traces
HTTP bodies
SQL statements
provider response bodies
arbitrary exception repr
~~~

Those belong in application observability systems with their own retention and access controls.

## 22. Domain Events provide causal operational evidence

A DomainEvent exposes:

~~~text
event_id
event_type
schema_version
aggregate_type
aggregate_id
occurred_at
actor_id
correlation_id
causation_id
~~~

This is useful when explaining which committed business fact triggered downstream work.

## 23. Domain Events are not a durable historical log by default

The built-in InProcessEventBus is synchronous, process-local and non-durable.

After restart, the bus does not itself provide a replayable historical event store.

## 24. Event subscribers can bridge into observability

An application can subscribe to selected event types and emit safe diagnostics:

~~~text
DomainEvent
      |
      v
application subscriber
      |
      +--> structured log
      +--> metric increment
      +--> trace annotation
~~~

## 25. Keep observability subscribers lightweight

Subscribers run synchronously.

Slow subscribers add latency to the command that published the event.

## 26. Subscriber failures propagate

If a subscriber raises, the exception propagates.

Because event publication happens after source commit, this can produce:

~~~text
source transaction committed ✅
subscriber failed             ❌
~~~

Your operational logs should preserve that distinction.

## 27. Post-commit failure is not rollback

Do not report a subscriber failure as if the source mutation automatically rolled back.

A useful incident record distinguishes:

~~~text
source_commit = success
post_commit_subscriber = failure
~~~

## 28. Timeline is customer history, not an operations log

Timeline is a selective projection of meaningful Activity, Task and Email lifecycle events.

It is useful when debugging what a customer-facing history shows, but it is not a complete mutation log.

## 29. Audit and Timeline answer different questions

~~~text
Audit
= operational mutation history

Timeline
= selected customer-facing history
~~~

Use the correct source during diagnosis.

## 30. Stable error codes are diagnostic anchors

Examples:

~~~text
contact.not_found
contact.archived
repository.duplicate
repository.deadlock
webhook.transport.timeout
webhook.transport.destination_forbidden
~~~

They work well in logs, alerts, runbooks and tests.

## 31. Error classes still matter

The broad class tells you the semantic family:

~~~text
ValidationError
NotFoundError
ConflictError
RepositoryError
IntegrationError
~~~

The code tells you the exact condition.

## 32. Repository diagnostics remain bounded

Translated SQLAlchemy/PostgreSQL failures may expose:

~~~text
sqlstate
constraint
table
column
~~~

They intentionally exclude SQL statement text and parameter values.

## 33. SQLSTATE can help operators classify failures

Examples:

~~~text
23505 -> repository.duplicate
40001 -> repository.serialization_failure
40P01 -> repository.deadlock
~~~

Applications can log both the stable PyCRMKit code and the safe SQLSTATE when present.

## 34. Do not reintroduce raw SQL diagnostics

If application code catches a lower-level driver exception before PyCRMKit translation, avoid logging raw params or full request-derived SQL data by default.

The adapter's safe error contract exists partly to prevent that leakage.

## 35. Webhook delivery state is persistent diagnostic evidence

WebhookDelivery exposes:

~~~text
state
attempt_count
next_attempt_at
last_attempt_at
completed_at
last_status_code
last_error_code
event_id
event_type
subscription_id
~~~

## 36. Webhook attempt history gives retry chronology

WebhookDeliveryAttempt records:

~~~text
attempt_number
attempted_at
outcome
status_code
error_code
next_attempt_at
~~~

This is useful when investigating repeated delivery failures.

## 37. Webhook diagnostics avoid raw response bodies

The stable delivery model retains bounded status/error information.

It does not make arbitrary remote response bodies part of the persistent diagnostic contract.

## 38. A webhook incident can be reconstructed safely

A typical investigation can join:

~~~text
event_id
      |
      v
WebhookDelivery
      |
      v
attempt history
      |
      +--> status codes
      +--> transport error codes
      +--> retry schedule
~~~

without logging the signing secret or request body.

## 39. Dead-letter state is operationally important

A delivery in DEAD_LETTER is terminal under the current delivery lifecycle.

Useful alert dimensions include:

~~~text
event_type
last_error_code
last_status_code
attempt_count
~~~

Avoid using unique event IDs as metric labels; keep those in logs or traces.

## 40. Email provider results also expose bounded diagnostics

EmailProviderResult provides:

~~~text
provider
status
provider_message_id
provider_metadata
failure_code
~~~

Provider adapters minimize failure metadata.

## 41. SMTP diagnostics are intentionally narrow

SMTP failure metadata can include:

~~~text
security
error_type
smtp_code
refused_recipient_count
~~~

without copying arbitrary SMTP exception prose.

## 42. Resend diagnostics expose useful provider metadata

Resend can retain safe metadata such as:

~~~text
request_id
status_code
rate_limit
rate_limit_remaining
rate_limit_reset
error_type
~~~

This is often enough to correlate an incident with provider-side support logs.

## 43. Provider request IDs are excellent correlation bridges

When an external provider returns a request identifier, log it alongside your own correlation ID.

Example:

~~~text
correlation_id = app-request-123
provider = resend
provider_request_id = req_abc
failure_code = resend.rate_limit_error
~~~

This bridges internal and provider investigations without exposing message content.

## 44. Application logs should include service context

Useful stable fields often include:

~~~text
service
environment
version
operation
result
actor_id
correlation_id
entity_type
entity_id
error_code
~~~

Deployment-specific fields remain application-owned.

## 45. Keep metrics low-cardinality

Good metric labels:

~~~text
operation
result
error_code
event_type
provider
delivery_state
~~~

Risky labels:

~~~text
contact_id
correlation_id
event_id
email
external_id
~~~

Unique identifiers belong in logs/traces rather than metric dimensions.

## 46. Trace systems can reuse correlation metadata

If the application uses distributed tracing, it can map or associate its trace/span IDs with CRM correlation metadata.

PyCRMKit does not require correlation_id to equal a vendor trace ID.

## 47. Do not overload correlation_id with every observability identifier

An application may have:

~~~text
trace_id
span_id
request_id
correlation_id
job_id
~~~

These can coexist.

Choose a clear contract for what correlation_id represents in your application.

## 48. HTTP middleware is a natural logging boundary

A FastAPI or Django application can:

~~~text
receive/generate correlation ID
      |
authenticate user
      |
bind actor_id
      |
call CRM
      |
log status + duration + safe identifiers
~~~

PyCRMKit does not own this middleware.

## 49. Background jobs need the same discipline

A scheduled import or worker should also bind:

~~~text
actor_id
correlation_id
~~~

before invoking the CRM facade.

For event-triggered work, prefer with_event when direct causation matters.

## 50. Correlation should survive async handoff

If your application places work onto a queue, persist/transport the safe correlation ID explicitly.

When consuming the message, reconstruct CRMContext.

This queue envelope is application-specific.

## 51. Causation should survive event-triggered handoff when needed

When a DomainEvent triggers queued child work, transport the parent EventId if the child should preserve direct causation.

Then reconstruct:

~~~text
actor
correlation
causation
~~~

at the consumer boundary.

## 52. Audit can verify what actually committed

If an application log says a command started but no matching Audit record exists, investigate whether the mutation failed or rolled back before commit.

This is especially useful for transaction debugging.

## 53. Domain Events can verify post-commit publication

If source state and Audit committed but a downstream subscriber failed, the event identity and correlation help isolate the post-commit step.

## 54. Timeline can verify projection outcomes

For supported event families, compare the DomainEvent source_event_id with the TimelineEntry source_event_id.

This helps distinguish:

~~~text
source mutation failure
projection failure
display/query issue
~~~

## 55. Never debug by dumping the whole database row first

Start with minimized operational evidence:

~~~text
correlation
actor
operation
entity ID
error code
audit action
event type
delivery state
safe provider metadata
~~~

Escalate access to raw CRM data only when genuinely necessary and authorized.

## 56. Use logging levels semantically

A practical application convention can be:

~~~text
DEBUG     diagnostic detail
INFO      successful application operation
WARNING   degraded or retryable behavior
ERROR     failed operation requiring investigation
CRITICAL  service-level failure or invariant break
~~~

PyCRMKit does not define these levels for the embedding application.

## 57. Not every domain error is an infrastructure incident

A contact.not_found or resource conflict may be an expected client/business outcome.

Severity should reflect operational impact rather than merely the existence of an exception.

## 58. Repository failures deserve stronger attention

Failures such as repository.deadlock, repository.serialization_failure and repository.backend_error are stronger candidates for infrastructure-oriented ERROR logs and metrics.

## 59. Retryable does not mean invisible

A retryable webhook/provider/database failure should still expose bounded evidence:

~~~text
retry_count
next_attempt_at
error_code
operation
correlation_id
~~~

## 60. Dead-letter state should be visible

Useful webhook operational signals include:

~~~text
dead_letter count
age of oldest dead letter
error-code distribution
event-type distribution
~~~

Unique event IDs should stay in logs/traces rather than metric labels.

## 61. Keep observability payloads bounded

Prefer counts, offsets and identifiers over serialized collections.

For pagination, useful fields include:

~~~text
limit
offset
total
has_next
has_previous
query type
~~~

## 62. Import jobs need batch-level observability

Useful import diagnostics include:

~~~text
source system
batch correlation ID
row count
success count
failure count
duplicate count
review count
duration
~~~

Raw source rows should not be logged by default.

## 63. Aggregate import failures by stable code

A summary by stable failure code is usually more useful and safer than storing every failed customer row in logs.

## 64. Merge operations deserve correlation-level traces

A Contact merge may touch Contacts, Activities, Relationships, Tags, Custom Fields, External Identities and Audit.

One correlation ID lets operators connect those effects without logging each payload.

## 65. Lead conversion is another cross-aggregate trace

A conversion can span Lead, Opportunity, Audit and Domain Events.

Treat the conversion as one correlation scope.

## 66. Webhook auto-delivery is post-commit work

When webhook_auto_delivery is enabled:

~~~text
source mutation
      |
      v
commit
      |
      v
DomainEvent publication
      |
      v
WebhookEventBridge
      |
      v
delivery attempt
~~~

A destination failure does not mean the source CRM mutation failed.

## 67. Distinguish source and side-effect results

A structured record can say:

~~~text
source_result = committed
side_effect = webhook
side_effect_result = retry_scheduled
error_code = webhook.http.503
~~~

This is more precise than one generic failure flag.

## 68. Preserve transaction boundaries in traces

For a command:

~~~text
started
      |
domain work
      |
commit
      |
post-commit side effects
      |
completed
~~~

do not emit a final success signal before the transactional facade call has actually completed.

## 69. Log exceptions once per ownership boundary

Avoid logging the same exception as ERROR in repository, service, router and middleware layers.

Choose clear logging ownership to prevent duplicate incidents.

## 70. Prefer machine-readable event names

Examples:

~~~text
crm.command.started
crm.command.completed
crm.command.failed
crm.webhook.retry_scheduled
crm.webhook.dead_letter
crm.provider.failed
~~~

Stable event names are easier to query and dashboard.

## 71. Duration belongs to application instrumentation

PyCRMKit does not expose a built-in command-duration metric.

Middleware or service wrappers can measure elapsed time using a monotonic clock.

Domain timestamps and operational latency are different concepts.

## 72. Audit and DomainEvent timestamps use the injected CRM Clock

That makes domain-time tests deterministic.

Request or job latency should be measured separately.

## 73. Allow-list provider metadata

If your application adds providers, copy selected safe metadata fields rather than entire provider responses.

This follows the existing SMTP and Resend adapter pattern.

## 74. Provider request IDs are valuable bridges

If a provider returns a request ID, log it beside your own correlation ID.

Example:

~~~text
correlation_id = app-request-123
provider = resend
provider_request_id = req_abc
failure_code = resend.rate_limit_error
~~~

This enables support correlation without message-body exposure.

## 75. Service context belongs in application logs

Useful fields can include:

~~~text
service
environment
version
operation
result
actor_id
correlation_id
entity_type
entity_id
error_code
~~~

Deployment-specific fields remain application-owned.

## 76. Keep metrics low-cardinality

Good labels:

~~~text
operation
result
error_code
event_type
provider
delivery_state
~~~

Risky labels:

~~~text
contact_id
correlation_id
event_id
email
external_id
~~~

Unique identifiers belong in logs/traces.

## 77. External tracing can coexist with CRM correlation

An application may have trace_id, span_id, request_id, correlation_id and job_id simultaneously.

PyCRMKit does not require correlation_id to equal a vendor tracing ID.

Define their relationship explicitly in application architecture.

## 78. HTTP middleware is a natural observability boundary

A FastAPI or Django application can:

~~~text
receive or generate correlation
      |
authenticate
      |
authorize
      |
bind actor_id
      |
call CRM
      |
log status, duration and safe IDs
~~~

PyCRMKit does not own this middleware.

## 79. Background jobs need the same context discipline

Scheduled jobs and queue consumers should bind actor_id and correlation_id before CRM calls.

Event-triggered child work should use with_event when direct causation matters.

## 80. Preserve context across queue handoff

If your application queues work, transport the safe correlation ID explicitly.

For event-triggered work, transport the parent EventId when you need causation to survive the handoff.

The queue envelope remains application-specific.

## 81. Audit helps verify commit outcome

If a command-start log exists but no corresponding Audit entry exists, investigate whether the transactional mutation failed or rolled back before commit.

## 82. Domain Events help isolate post-commit failures

If source state and Audit exist but a downstream subscriber failed, event ID, correlation and causation help locate the failure after commit.

## 83. Timeline can verify projection behavior

For supported projections, TimelineEntry.source_event_id matches the source DomainEvent ID.

This helps distinguish source mutation issues from projection/display issues.

## 84. Start incident investigation with minimized evidence

A good first-pass dataset is:

~~~text
correlation ID
actor ID
operation
entity ID
error code
Audit actions
event type / ID
webhook delivery state
safe provider metadata
~~~

Escalate access to raw CRM data only when authorized and necessary.

## 85. Retention and access controls still matter

Even minimized observability data can expose entity IDs, actor IDs, operation names, failure patterns and system topology.

Logging/tracing platforms should be protected as production systems.

## 86. Runbooks should use stable codes

Runbooks can anchor on conditions such as:

~~~text
repository.deadlock
webhook.transport.destination_forbidden
contact.archived
~~~

Stable codes are more reliable than message fragments.

## 87. Test observability contracts

If dashboards depend on fields such as event, operation, result, correlation_id and error_code, write tests asserting those fields and privacy rules.

## 88. Test correlation propagation

A useful test proves:

~~~text
request or job correlation
      |
      v
CRMContext
      |
      +--> DomainEvent
      +--> Audit
      +--> application log
~~~

## 89. Test webhook attempt diagnostics

With a fake transport returning HTTP 503, verify:

~~~text
delivery.state = retry_scheduled
last_status_code = 503
last_error_code = webhook.http.503
attempt.outcome = retry_scheduled
~~~

No real network is required.

## 90. Test public-safe error logging

An application logging helper can use error.as_dict for context intended for ordinary structured logs, then test that sensitive keys are redacted.

## Common mistakes

### Generating a new correlation ID at every layer

This destroys end-to-end traceability.

### Logging whole CRM entities or raw request bodies

Those can contain PII and arbitrary metadata.

### Logging raw SQL params

PyCRMKit deliberately removes them from translated persistence errors.

### Dumping complete provider responses

Prefer allow-listed metadata.

### Treating Domain Events as a durable event store

The built-in bus is synchronous and process-local.

### Treating Timeline as full mutation history

Use Audit for operational mutation history.

### Treating Audit as a stack-trace store

Audit should stay minimized and domain-oriented.

### Logging one exception at every layer

This produces duplicate incidents and noisy alerts.

### Alerting on every 404 or conflict

Expected business outcomes are not always infrastructure incidents.

### Using unique IDs as metric labels

This creates high-cardinality metrics.

### Assuming a subscriber failure rolled back the source mutation

Event publication happens after commit.

### Logging a secret through direct field access because repr hides it

repr protection does not make explicit secret logging safe.

### Using wall-clock timestamps to calculate latency

Use monotonic elapsed time for application duration measurement.

## Observability checklist

A production application should be able to answer yes to questions like:

~~~text
Can one correlation follow a request or job end-to-end?             ✅
Can Audit be queried by correlation?                                ✅
Are stable error codes included in diagnostics?                     ✅
Are raw customer payloads absent from ordinary logs?                 ✅
Are SQL params absent from persistence diagnostics?                  ✅
Can webhook retries and dead letters be inspected?                  ✅
Are provider request IDs retained when safely available?             ✅
Can post-commit failure be distinguished from source rollback?       ✅
Are log fields machine-readable and stable?                          ✅
Are metric labels bounded-cardinality?                               ✅
Are observability privacy rules regression-tested?                  ✅
~~~

## What you learned

You can now explain:

- why PyCRMKit provides observability primitives rather than an observability platform;
- how actor, correlation and causation relate;
- how to propagate context through HTTP, jobs and event-triggered work;
- how Audit supports persistent investigation;
- how Domain Events support causal debugging;
- why Timeline has a different role;
- how stable error codes and safe persistence diagnostics help operations;
- how webhook delivery/attempt records expose retry evidence;
- how provider failure codes and request IDs help external-service diagnosis;
- why post-commit subscriber failures differ from rollback;
- how to design privacy-safe structured logs and bounded metrics.

## LEVEL 7 in progress

~~~text
33 Testing PyCRMKit Applications ✅
34 Observability & Debugging      ✅
35 Performance                    ← NEXT
36 Application Architecture
37 Production Deployment
38 Complete FastAPI Application
39 Complete Django Application
40 Zero-to-Hero Final Project
~~~

## Next

The next chapter is **35 - Performance**.

The next architecture is:

~~~text
application workload
      |
      +--> pagination
      +--> search
      +--> timeline queries
      +--> bulk import
      +--> event publication
      +--> database queries
      |
      v
measure
      |
      v
baseline
      |
      v
optimize verified bottlenecks
~~~

The next learning question is:

> How should a production application measure and optimize PyCRMKit workloads without mistaking synthetic benchmark guardrails for real production capacity or latency guarantees?
