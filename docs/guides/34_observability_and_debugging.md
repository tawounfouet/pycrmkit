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
