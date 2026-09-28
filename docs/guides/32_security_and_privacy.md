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


## 11. Audit minimization

AuditEntry.changes is explicit evidence, not a full entity snapshot.

AuditService.record_event does not automatically copy DomainEvent.payload.

Webhook registration audit records safe field names. Secret rotation records:

~~~text
["signing_secret"]
~~~

The old and new secret values are never written into Audit changes. Actor and correlation metadata still provide operational traceability.

## 12. Webhook signing-secret storage

Webhook delivery needs signing key material later, so supported persistence adapters store the configured signing secret as application data.

PyCRMKit does not claim transparent encryption-at-rest for that field.

Production deployments must protect databases and backups through their normal encryption and access-control mechanisms.

Secrets should not be committed to source control. Test fixtures should use dummy values.

## 13. Secret generation and validation

If the application does not provide a webhook secret, PyCRMKit generates one with:

~~~text
secrets.token_urlsafe(32)
~~~

Supplied signing secrets are normalized and validated. Their UTF-8 encoded length must be between 16 and 512 bytes.

Validation errors do not echo the secret.

## 14. Webhook secret rotation

The public facade supports:

~~~python
crm.webhooks.rotate_secret(
    subscription.id,
    signing_secret="new-secret-material",
)
~~~

If signing_secret is omitted, PyCRMKit generates fresh material.

The flow is:

~~~text
load subscription
      |
normalize/generate candidate
      |
compare safely
      |
persist change
      |
audit field name only
      |
commit
~~~

The entity uses hmac.compare_digest when checking whether the candidate is already active. Reusing the current secret is idempotent.

Applications remain responsible for distributing the new secret to consumers through their own secure channel.

## 15. Webhook HMAC integrity

Webhook signing uses:

~~~text
v1=HMAC_SHA256(
    secret,
    "<unix_timestamp>.<payload_bytes>"
)
~~~

Both timestamp and payload bytes are covered by the signature.

Verification uses hmac.compare_digest.

The integrity-only call remains supported:

~~~python
verify_webhook_signature(
    secret,
    timestamp,
    payload,
    signature,
)
~~~

## 16. Replay-age validation

Internet-facing receivers can additionally pass current_timestamp and tolerance_seconds.

The default tolerance is 300 seconds.

~~~text
difference = 300 seconds -> accepted
difference = 301 seconds -> rejected
~~~

HMAC integrity and replay-age checking are distinct protections: an old message can have a valid HMAC and still be rejected as stale.

## 17. Webhook URL validation

Registration rejects:

~~~text
non-HTTP(S) schemes
missing host
embedded username/password
fragments
whitespace / header-injection forms
oversized URLs
~~~

Hostnames are normalized through IDNA.

For example:

~~~text
https://user:password@example.com/hook
~~~

is rejected.

## 18. Private-network and SSRF protection

StdlibWebhookTransport defaults to:

~~~text
allow_private_networks = False
~~~

Before sending, literal IP addresses are checked and hostnames are resolved.

Every destination address must be globally routable.

Non-public destinations raise:

~~~text
webhook.transport.destination_forbidden
~~~

DNS resolution failures use:

~~~text
webhook.transport.dns_error
~~~

Private-network delivery is an explicit opt-in.

Enabling it changes the trust model and becomes the embedding application's responsibility.

## 19. Redirects are disabled

The built-in stdlib webhook transport refuses redirect requests.

A configured public URL therefore cannot automatically redirect the built-in transport into a different internal/private target.

## 20. Webhook delivery diagnostics

Transport failures use stable codes such as:

~~~text
webhook.transport.timeout
webhook.transport.network_error
webhook.transport.dns_error
webhook.transport.destination_forbidden
~~~

Persistent delivery state keeps bounded diagnostics such as last status code, last error code, attempt count and next-attempt time.

The canonical event payload is persisted for retry purposes, but payload_json is excluded from repr.

## 21. Conservative destructive operations

The stable public facades intentionally avoid generic:

~~~text
delete
purge
hard_delete
~~~

for important CRM namespaces.

Instead lifecycle operations are explicit:

~~~text
Contact       -> archive
Organization  -> archive
Relationship  -> end
Webhook       -> disable
External ID   -> detach
Duplicate     -> merge + archive
~~~

The security suite locks this boundary.

## 22. Archived-record mutation protection

Archived Contacts cannot be updated through the public facade.

Stable failure:

~~~text
InvalidStateError
code = contact.archived
~~~

Organizations have the corresponding immutable-after-archive guard.

Archive therefore changes what mutations are allowed; it is not merely a query filter.

## 23. Duplicate merge provenance

The default merge policy is conservative.

It requires duplicate provenance by default.

Primary and duplicate must be different records.

Provenance must correspond to the duplicate candidate and must support a duplicate decision.

## 24. Blocking merge conflicts cannot be bypassed

Even if a caller constructs provenance whose decision says duplicate, a blocking conflict forces rejection.

Stable code:

~~~text
merge.provenance.blocking_conflict
~~~

Qualified context stores signal names rather than underlying matched sensitive values.

## 25. Contact-point merge conflicts are conservative

Different primary emails reject by default.

Different primary phones reject by default.

Custom-field conflicts are conservative by default.

Merge runs transactionally so rejected operations do not leave partial state.

Full DedupProvenance can itself contain CRM evidence and must be treated as CRM data.

Persisted merge audit is intentionally minimized to identifiers, score, decision, signal names, conflict descriptors, statistics and policy rather than matched email/phone/custom-identifier values.


## 26. Authorization remains application-owned

Security-safe lifecycle semantics do not answer whether a caller is authorized.

FastAPI and DRF actor/correlation context does not prove identity or permission.

The embedding application must authenticate and authorize before invoking sensitive commands.

After authorization, it can bind the authenticated actor ID into CRMContext for traceability.

## 27. Layered model

The intended model is:

~~~text
application authentication / authorization
      |
      v
PyCRMKit validation / lifecycle / transaction rules
      |
      v
privacy-minimized errors / events / audit / repr
      |
      v
database / backup / network / secret-store controls
~~~

No one layer replaces the others.

## 28. Dedicated Security & Privacy qualification

The workflow is:

~~~text
.github/workflows/security-privacy.yml
~~~

It first runs:

~~~text
pytest tests/security -q
~~~

against the source checkout.

Then it builds the distribution and creates a clean virtual environment.

The same suite is run against the installed wheel with PYTHONPATH empty.

This proves the hardening behavior is actually packaged for consumers.

## 29. Current security-regression coverage

The current suite verifies:

~~~text
recursive sensitive-error redaction
secret-safe repr
PII-free default diagnostics
Contact event/audit minimization
External Identity event minimization
webhook HMAC integrity
webhook replay-age rejection
secret rotation and audit privacy
unsafe webhook URL rejection
absence of generic hard-delete facade methods
archived Contact mutation rejection
merge provenance requirement
blocking-conflict merge rejection
~~~

## 30. Practical application guidance

Load production credentials through application configuration or the application's secret-management system.

Do not commit production credentials to source control.

Use dummy values in tests.

Keep actor_id and correlation_id non-secret.

Prefer logs such as:

~~~text
operation=contact.update
contact_id=...
correlation_id=...
fields=["display_name", "source"]
result=success
~~~

instead of full CRM aggregate dumps.

Use error.as_dict or the HTTP error bridges at public boundaries.

Treat raw error.context as potentially sensitive.

Protect databases and backups containing CRM PII, webhook signing secrets, delivery payloads, External Identities and communication metadata.

Enable private-network webhook delivery only when intentional.

Use replay-age verification for internet-facing webhook receivers.

Use the public secret-rotation API so persistence and audit semantics remain consistent.

## Common mistakes

### Assuming safe repr means encryption

repr suppression only reduces diagnostic exposure.

### Assuming public redaction modifies raw error.context

It does not.

### Logging raw error.context after relying on as_dict privacy

Raw context can still be sensitive.

### Putting secrets into error.message

Context redaction does not sanitize arbitrary message prose.

### Copying full Contact payloads into Audit

Prefer minimized field/evidence metadata.

### Copying external_id into events unnecessarily

The V1 event contract intentionally omits it.

### Treating webhook HMAC as business authorization

HMAC verifies shared-secret possession and message integrity, not user permissions.

### Verifying HMAC without freshness checking on internet receivers

A previously valid request can otherwise be replayed.

### Allowing arbitrary redirects

The built-in stdlib transport deliberately refuses redirects.

### Opting into private webhook networks without considering SSRF exposure

The opt-in changes the network trust model.

### Storing production secrets in source control

repr/redaction cannot undo that disclosure.

### Treating actor_id as authenticated identity

Authentication and authorization must happen in the embedding application.

### Adding generic hard-delete methods for convenience

The stable public API intentionally uses lifecycle operations.

### Merging without trustworthy provenance

The default merge contract is conservative by design.

### Treating security regression tests as penetration-test certification

They qualify documented invariants, not external certification.

## Testing security and privacy

Application/security tests should cover:

~~~text
public error redaction
raw versus public error context
no validation echo of customer values
secret-safe repr
event payload minimization
audit minimization
HMAC tamper detection
replay-age boundaries
unsafe webhook URLs
private destination policy
secret rotation
destructive-action boundary
archived mutation rejection
merge provenance/conflict safeguards
installed-wheel hardening
~~~

## What you learned

You can now explain:

- the V1 security/privacy scope;
- application-owned authentication and authorization;
- primary CRM data versus secondary copies;
- recursive error redaction;
- raw error-context sensitivity;
- secret-safe repr;
- SMTP and Resend credential handling;
- event and audit minimization;
- External Identity event privacy;
- webhook secret persistence scope;
- secret generation and rotation;
- HMAC-SHA256 signing;
- replay-age validation;
- webhook URL validation;
- private-network blocking;
- redirect refusal;
- conservative destructive operations;
- merge provenance safeguards;
- database/operator responsibility;
- source and installed-wheel security qualification.
