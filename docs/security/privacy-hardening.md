# Security & Privacy Hardening

PyCRMKit `1.0.0b1` hardens the V1 candidate surface without introducing a new
CRM domain capability.

The milestone verifies:

```text
PII-safe diagnostics
secret handling
webhook signatures
input validation
destructive-action safeguards
duplicate-merge safeguards
event-payload redaction
```

## Privacy-first diagnostics

PyCRMKit does not log full CRM customer payloads by default.

Preferred operational metadata remains:

```text
entity ID
operation
result
correlation ID
error code
safe field names
```

rather than:

```text
email
phone
postal address
message body
provider credential
external customer identifier
```

### Public error serialization

`PyCRMKitError.as_dict()` now recursively redacts values carried by sensitive
keys such as:

```text
email
phone
address
external_id
password
secret
signing_secret
api_key
authorization
token
message/body fields
```

The FastAPI and DRF error bridges use the same privacy rule.

The in-process `error.context` attribute remains diagnostic state and should be
treated as potentially sensitive when applications construct custom errors.

Core validators have also been changed so invalid email/phone/domain/external
identity values are not copied into error contexts unnecessarily.

## Secret handling

Secret-bearing objects must not expose credentials through ordinary `repr()`.

Qualified examples include:

```text
WebhookSubscription.signing_secret
WebhookSubscription.url
WebhookRequest.url/body/headers
SMTPConfig.password
ResendConfig.api_key
```

Webhook URLs and request headers are intentionally excluded from repr because
they may contain deployment-specific sensitive routing/authentication material.

### Webhook secret storage

PyCRMKit needs webhook signing key material at delivery time, so supported
persistence adapters store the configured signing secret as application data.

PyCRMKit does not claim transparent encryption-at-rest for that field.

Production deployments must protect the database and backups using the
operator's normal encryption/access-control controls.

Secrets must never be committed to source control, test fixtures must use dummy
values, and audit records must store only the fact that a secret changed.

## Webhook secret rotation

The public facade now supports:

```python
rotated = crm.webhooks.rotate_secret(
    subscription.id,
    signing_secret="new-secret-material",
)
```

If `signing_secret` is omitted, PyCRMKit generates a fresh high-entropy secret.

Rotation:

```text
loads the subscription
normalizes/generates new key material
updates the persisted subscription
records webhook.subscription.secret_rotated
stores only ["signing_secret"] in audit changes
never records the old or new secret value
```

Supplying the already-active secret is idempotent and does not create a second
rotation audit record.

Applications should distribute the new secret to webhook consumers using their
own secure secret-management channel.

## Webhook signatures and replay age

Signing remains:

```text
v1=HMAC_SHA256(secret, "<unix_timestamp>.<payload_bytes>")
```

Comparison uses `hmac.compare_digest`.

The verification helper remains backward-compatible for integrity-only checks:

```python
verify_webhook_signature(secret, timestamp, payload, signature)
```

For internet-facing webhook receivers, V1 recommends timestamp freshness
verification:

```python
verify_webhook_signature(
    secret,
    timestamp,
    payload,
    signature,
    current_timestamp=now,
    tolerance_seconds=300,
)
```

A timestamp outside the configured tolerance is rejected even when the HMAC is
otherwise valid.

The timestamp and payload are both covered by the signature, so modifying either
invalidates the signature.

## Webhook destination validation

Webhook registration already rejects:

```text
non-HTTP(S) schemes
missing host
embedded username/password
fragments
whitespace/header-injection forms
oversized URLs
```

The built-in stdlib transport additionally rejects redirects and destinations
that resolve to non-public IP addresses by default.

Private-network delivery remains an explicit opt-in through the transport
configuration.

## Input validation

Security qualification covers the principle:

```text
untrusted input
    ↓
parse / normalize
    ↓
validate
    ↓
domain operation
```

Examples include:

```text
email / phone normalization
webhook URL validation
webhook secret length validation
event type validation
pagination bounds
external identity length/system validation
import structural validation
FastAPI request validation
DRF serializer validation
```

FastAPI validation details expose error type/location/message without echoing
the submitted input object.

## Event payload privacy

Domain events should carry the minimum data needed for integration and
automation.

Contact create/update/archive events do not copy full Contact values into the
event payload.

External Identity events now expose:

```text
system
```

but no longer copy:

```text
external_id
```

into the emitted event payload.

The External Identity value remains available through the explicit repository
or facade lookup for authorized application code.

Email lifecycle events retain delivery state/provider metadata but not message
body or recipient values.

## Merge provenance privacy

Full `DedupProvenance` may contain matched values and therefore remains an
application-facing result object that must be handled as CRM data.

The persisted `contact.merged` audit entry retains only:

```text
candidate entity ID
score
decision
matched signal names
conflict signal/severity/key
merge statistics
merge policy
```

Matched email/phone/custom-identifier values are not copied into audit history.

## Duplicate merge safeguards

The default merge contract remains conservative:

```text
primary and duplicate must be different
explicit primary ID required
explicit duplicate ID required
duplicate provenance required by default
provenance candidate must match duplicate ID
provenance decision must be duplicate
primary email conflict → reject
primary phone conflict → reject
custom-field conflict → reject
transaction rolls back on failure
duplicate is archived, not physically deleted
```

`1.0.0b1` adds one additional integrity guard:

```text
provenance with any BLOCKING conflict → reject merge
```

This prevents a caller from forging a `duplicate` decision around evidence the
deduplication model itself classifies as blocking.

## Destructive-action safeguards

The V1 candidate facade deliberately exposes no generic:

```text
delete()
purge()
hard_delete()
```

for primary CRM aggregates.

Lifecycle operations remain explicit:

```text
Contact     → archive
Organization→ archive
Relationship→ end
Webhook     → disable
External ID → detach
Duplicate   → merge + archive
```

Archived Contacts and Organizations reject later profile mutation.

Detach/disable operations are explicit and idempotent where documented.

## Authorization boundary

PyCRMKit is a headless domain framework, not an identity or authorization
provider.

Applications remain responsible for deciding **who** may call destructive or
sensitive operations.

PyCRMKit provides deterministic validation, transaction boundaries, audit
context and safe defaults; the embedding application must enforce its own
authentication and permission policy before invoking those operations.

## Security qualification gate

The dedicated workflow:

```text
.github/workflows/security-privacy.yml
```

runs the security/privacy regression suite twice:

```text
source checkout
built wheel in a clean virtual environment with PYTHONPATH=""
```

The suite verifies:

```text
sensitive error redaction
secret-safe repr behavior
PII-free default diagnostics
event payload minimization
external identity event redaction
webhook HMAC integrity
webhook replay-age rejection
secret rotation + audit privacy
unsafe webhook URL rejection
absence of generic hard-delete facade methods
archived-record mutation rejection
default merge provenance requirement
blocking-conflict merge rejection
```

## Scope boundary

This milestone does not claim:

```text
application authorization/RBAC
database transparent encryption
external secrets-manager integration
formal cryptographic key escrow
penetration testing certification
performance guarantees
full dependency compatibility matrix
```

Those concerns are either application/operator responsibilities or later V1
qualification work.

The next milestone is:

```text
1.0.0b2 — Performance Baseline
```
