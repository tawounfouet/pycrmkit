# Security & Privacy

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter closes **LEVEL 6 - Persistence & Integrations**.

Security and privacy cross every layer introduced so far:

~~~text
untrusted or sensitive data
      |
      +--> validation
      +--> errors
      +--> repr / diagnostics
      +--> audit
      +--> events
      +--> webhooks
      +--> persistence
      |
      v
explicit trust and minimization boundaries
~~~

The central rule is:

> PyCRMKit stores CRM data when the application needs that data, but it deliberately minimizes where sensitive values are copied, rendered, logged, audited, emitted or exposed as diagnostics.

The V1 hardening model combines:

~~~text
privacy-safe diagnostics
secret-safe representations
event and audit minimization
conservative destructive actions
webhook HMAC and replay controls
webhook destination controls
transactional consistency
application-owned authorization
operator-owned storage protection
~~~

## What you will learn

You will learn to:

- understand the V1 security/privacy scope;
- distinguish primary CRM data from secondary exposure surfaces;
- understand recursive public-error redaction;
- understand why raw error context can remain sensitive;
- understand secret-safe repr behavior;
- understand SMTP and Resend credential handling;
- understand event and audit minimization;
- understand webhook signing-secret lifecycle;
- understand HMAC integrity and replay-age validation;
- understand webhook URL and network-destination safeguards;
- understand conservative lifecycle/destructive operations;
- understand duplicate-merge safeguards;
- understand the application authorization boundary;
- understand database/encryption responsibility;
- understand the dedicated Security & Privacy qualification workflow;
- close LEVEL 6.

## 1. Scope boundary

PyCRMKit is a headless domain framework. It is not an authentication or authorization provider.

The embedding application remains responsible for deciding who may invoke sensitive operations such as:

~~~text
archive Contact
archive Organization
end Relationship
detach External Identity
disable Webhook
rotate Webhook secret
merge duplicate Contacts
expose or export CRM data
~~~

PyCRMKit then enforces its own domain, state and transaction invariants after the application has authorized the operation.

The stable V1 security documentation explicitly does not claim:

~~~text
application RBAC
transparent database encryption
external secret-manager integration
formal cryptographic key escrow
penetration-testing certification
~~~

## 2. Primary CRM data versus secondary copies

A CRM necessarily stores business/customer data such as:

~~~text
name
email
phone
address
metadata
external identifiers
communication state
~~~

Privacy hardening does not mean the canonical CRM record stops storing those values. Instead, PyCRMKit minimizes unnecessary copies in:

~~~text
errors
logs
repr
audit
events
retry diagnostics
provider failure metadata
~~~

Operational evidence therefore prefers metadata such as entity IDs, operation, result, correlation ID, error code, safe field names, status code and constraint name rather than raw customer payloads.

## 3. Public error redaction

Public PyCRMKit errors use:

~~~text
code
message
context
~~~

PyCRMKitError.as_dict applies recursive redaction to sensitive context keys. FastAPI and DRF use the same privacy rule.

Sensitive keys include:

~~~text
address
api_key
authorization
body
credential
credentials
email
external_id
html_body
idempotency_key
message_body
password
phone
postal_address
recipient
sender
secret
signing_secret
text_body
token
~~~

Keys ending in these suffixes are also treated as sensitive:

~~~text
_api_key
_password
_secret
_token
~~~

The public marker is:

~~~text
[REDACTED]
~~~

Safe siblings such as contact_id, sqlstate, constraint, table and column can remain visible when useful.

Redaction does not mutate error.context itself. Trusted in-process code can still see the original diagnostic context, so raw error.context must not be assumed safe for public logging.

Redaction is key-based. If an application hides a secret under a misleading key, PyCRMKit cannot reliably infer the sensitivity. Error messages themselves must therefore also avoid raw secrets or PII.

## 4. Validation does not echo customer contact points

Contact email and phone validators avoid copying malformed raw values into public error context. The security suite verifies malformed Contact data does not appear in public errors or default logs.

External Identity errors similarly avoid copying the provider-owned external identifier into public context. A not-found context carries the normalized system but not external_id. Ownership-conflict context carries safe ownership metadata without echoing the provider identifier.

## 5. Persistence diagnostics are bounded

SQLAlchemy/PostgreSQL failures are translated before crossing the adapter boundary.

Safe context may contain:

~~~text
sqlstate
constraint
table
column
~~~

It deliberately excludes:

~~~text
SQL statement
SQL params
raw driver dump
~~~

SQL parameters can contain customer values or credentials, so PyCRMKit creates stable generic messages instead of forwarding arbitrary driver text.

## 6. Secret-safe repr

repr output is a security surface because it appears in REPL sessions, debug consoles, test failures, exception locals and logs.

Qualified V1 examples exclude sensitive fields from repr:

~~~text
SMTPConfig.password
ResendConfig.api_key
WebhookSubscription.signing_secret
WebhookSubscription.url
WebhookRequest.url
WebhookRequest.body
WebhookRequest.headers
WebhookDelivery.payload_json
~~~

This reduces accidental diagnostic exposure. It does not encrypt the stored value.

## 7. SMTP credential handling

SMTPConfig stores password with repr disabled. Username and password must be configured together.

SMTP failure results retain bounded operational metadata such as security mode, error type, SMTP code and refused-recipient count rather than copying arbitrary exception text.

## 8. Resend credential handling

ResendConfig stores api_key with repr disabled.

The synchronous Resend SDK uses module-level api_key state. PyCRMKit serializes the set/send/restore sequence with a lock:

~~~text
acquire lock
      |
save previous SDK key
      |
set provider key
      |
send
      |
restore previous key in finally
      |
release lock
~~~

Provider results retain bounded metadata such as request IDs and rate-limit fields rather than raw request/response payloads.

## 9. Event payload minimization

Domain Events are integration contracts. Anything in a public event payload may leave the source process through subscribers or webhooks.

The security suite creates a Contact containing email, phone, street address and private metadata and verifies those values do not appear in serialized contact.created.

Contact audit evidence is minimized too. ContactsAPI.create records field names through present_fields instead of storing full supplied values. Updates use revision_fields to record which DTO fields were supplied rather than their values.

## 10. External Identity event privacy

The stable External Identity event payload is:

~~~text
{"system": "legacy_crm"}
~~~

It intentionally does not include external_id.

The provider-owned identifier remains available through explicit authorized repository/facade APIs; it is simply not copied into the public event stream.
