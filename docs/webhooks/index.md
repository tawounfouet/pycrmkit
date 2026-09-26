# Webhook Registrations

`0.5.0b1` introduces persistent webhook registration and filtering. It does
not yet perform outbound HTTP delivery.

## Public API

```python
subscription = crm.webhooks.register(
    url="https://example.com/hooks/crm",
    events=[
        "contact.created",
        "opportunity.won",
    ],
)

active = crm.webhooks.list(enabled=True)

crm.webhooks.disable(subscription.id)
```

`crm.webhooks.list(...)` supports exact event-type and enabled/disabled
filters with normal PyCRMKit offset pagination.

## Subscription model

A registration contains:

```text
WebhookSubscriptionId
created_at
updated_at
url
event_types
disabled_at
```

`enabled` is derived from `disabled_at`.

Event types are normalized, deduplicated and sorted. A subscription matches an
event only when it is enabled and the event type is explicitly registered on
the subscription.

## Event registry boundary

Registration only accepts event types known to the configured
`EventRegistry`.

By default, `CRM.memory()` uses `default_event_registry()`, which contains
the stable public event contracts from PyCRMKit `0.1`–`0.4`.

Applications with custom public events may supply their own registry:

```python
from pycrmkit import CRM
from pycrmkit.events import EventRegistry

registry = EventRegistry()
registry.register("customer.enriched", 1)

crm = CRM.memory(event_registry=registry)
crm.webhooks.register(
    url="https://example.com/hooks/custom",
    events=["customer.enriched"],
)
```

## URL registration rules

Registration validates endpoint syntax only:

- scheme must be `http` or `https`;
- a host is required;
- embedded username/password credentials are rejected;
- URL fragments are rejected;
- host names are normalized to IDNA/lowercase form.

No network request occurs during registration.

Transport-time controls such as DNS/IP policy, SSRF protection, TLS policy,
timeouts and response handling belong to the delivery engine milestone.

## Persistence and audit

Webhook registrations participate in the same Unit of Work abstraction as
other PyCRMKit domains. The Memory adapter is the qualified implementation in
this beta.

Registration and the first disable operation write privacy-conscious audit
entries. Re-disabling an already disabled registration is idempotent and does
not create another audit entry.

Webhook-management mutations do not emit new domain events in this milestone.
This avoids self-triggering delivery behavior before the delivery engine exists.

## Deferred to 0.5.0b2

The following are intentionally absent:

```text
HTTP transport
HMAC signing
retry
backoff
delivery attempts/logs
external-delivery idempotency
dead-letter state
response policy
```
