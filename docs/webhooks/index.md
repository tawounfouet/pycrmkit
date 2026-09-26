# Webhooks

PyCRMKit `0.5.0b2` combines persistent webhook registrations with an explicit,
retryable delivery engine.

## Registration

```python
subscription = crm.webhooks.register(
    url="https://example.com/hooks/crm",
    events=["contact.created", "opportunity.won"],
    signing_secret="replace-with-a-strong-secret",
)
```

If no signing secret is supplied, PyCRMKit generates one. Secrets are excluded
from entity representations and audit changes.

Subscriptions continue to support exact event filtering and idempotent disable:

```python
crm.webhooks.list(enabled=True, event_type="contact.created")
crm.webhooks.disable(subscription.id)
```

## Explicit delivery

`0.5.0b2` intentionally keeps delivery explicit:

```python
deliveries = crm.webhooks.deliver(event)
```

Automatic subscription to the CRM event bus is reserved for the release
candidate so the engine can be qualified independently first.

One `WebhookDelivery` exists for each:

```text
(subscription_id, event_id)
```

This pair is the idempotency boundary. Replaying the same event for the same
subscription reuses the existing delivery and does not resend a terminal
successful/dead-letter delivery.

## Signed request

The canonical `EventSerializer` JSON becomes the HTTP body. Requests include:

```text
Content-Type: application/json
X-PyCRMKit-Delivery-ID
X-PyCRMKit-Event-ID
X-PyCRMKit-Event-Type
X-PyCRMKit-Idempotency-Key
X-PyCRMKit-Timestamp
X-PyCRMKit-Signature
```

The signature is:

```text
v1=HMAC_SHA256(secret, "<unix_timestamp>.<payload_bytes>")
```

Receivers can use `verify_webhook_signature(...)` for constant-time
verification.

## Retry policy

The default policy is deterministic exponential backoff:

```text
attempt 1 failure → 10 s
attempt 2 failure → 20 s
attempt 3 failure → 40 s
...
cap → 10 min
max attempts → 5
```

Retryable HTTP responses are:

```text
408
425
429
5xx
```

Transport timeout/network failures are retryable. Other 3xx/4xx responses are
terminal and enter dead-letter state immediately.

`crm.webhooks.retry_due()` processes retries whose scheduled time has arrived.

## Delivery history

```python
crm.webhooks.deliveries(state="retry_scheduled")
crm.webhooks.attempts(delivery.id)
```

Each processing attempt records only safe delivery metadata:

```text
attempt_number
attempted_at
outcome
status_code
error_code
next_attempt_at
```

Response bodies and exception messages are not persisted.

The canonical event JSON is retained on the delivery state so a retry can occur
after the original in-process event callback has returned. It is marked
secret-sensitive in representations because event payloads may contain CRM data.

## Transport security

`StdlibWebhookTransport` uses only the Python standard library. By default it:

- permits only the already-validated HTTP(S) subscription URL;
- rejects destinations that resolve to non-public IP addresses;
- rejects redirects rather than following them;
- normalizes timeout/network failures into safe error codes.

Private-network delivery can be enabled explicitly on the transport for trusted
environments and local integration tests.

These checks reduce common SSRF exposure but are not presented as a complete
network-isolation boundary. Production deployments should still enforce
appropriate egress controls.

## Scope boundary

`0.5.0b2` does not automatically subscribe the delivery engine to all CRM
Domain Events. That integration and the complete
create → emit → match → sign → deliver → retry → history scenario belong to
`0.5.0rc1`.
