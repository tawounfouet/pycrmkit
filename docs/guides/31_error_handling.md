# Error Handling

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

The previous chapters established:

~~~text
domain operations
      ↓
transaction boundary
      ↓
context / events / audit
      ↓
HTTP and persistence adapters
~~~

This chapter defines how failures cross those boundaries without leaking
adapter internals, SQL parameters, secrets or raw customer input.

The central architecture is:

~~~text
domain / repository / integration failure
      |
      v
PyCRMKitError hierarchy
      |
      +--> stable code
      +--> public message
      +--> structured context
      |
      v
privacy-safe serialization
      |
      +--> FastAPI mapping
      +--> DRF mapping
      +--> application logs / diagnostics
      |
      v
public error contract
~~~

The central rule is:

> Error classes describe semantic failure families. Stable error codes describe
> precise machine-readable conditions. Adapters may translate implementation
> failures, but they must not leak implementation details across the public
> boundary.

## What you will learn

You will learn to:

- understand the public PyCRMKit exception hierarchy;
- distinguish exception class from stable error code;
- understand structured error context;
- understand privacy-safe error serialization;
- understand recursive sensitive-key redaction;
- understand domain validation errors;
- understand not-found errors;
- understand conflict, duplicate and invalid-state errors;
- understand repository failures;
- understand integration failures;
- understand SQLAlchemy/PostgreSQL translation;
- understand safe SQLSTATE/constraint/table/column diagnostics;
- understand what database information is deliberately excluded;
- understand Django transaction error normalization;
- understand FastAPI status mapping;
- understand DRF status mapping;
- distinguish transport validation from domain validation;
- understand FastAPI request validation as 422;
- understand DRF request validation as 400;
- understand validation-detail privacy;
- understand fallback handling for unknown exceptions;
- understand how stable error codes support clients and tests;
- prepare for Security & Privacy.

# Public exception hierarchy

## 1. PyCRMKitError is the public base class

The root type is:

~~~text
PyCRMKitError
~~~

It represents a typed, machine-readable PyCRMKit failure.

## 2. Every public error carries three pieces of information

~~~text
message
code
context
~~~

## 3. message is human-readable

Example:

~~~text
Contact not found
~~~

The message explains the failure to a human.

## 4. code is machine-readable

Example:

~~~text
contact.not_found
~~~

Client logic should prefer stable codes over parsing messages.

## 5. context is structured metadata

Example:

~~~python
{
    "contact_id": "c-123"
}
~~~

Context gives callers useful diagnostic information without requiring them to
parse prose.

## 6. Exception class and error code are different contracts

The class answers:

> Which broad semantic family does this failure belong to?

The code answers:

> Which precise failure condition occurred?

## 7. The default base code is pycrmkit.error

A bare PyCRMKitError uses:

~~~text
pycrmkit.error
~~~

unless the caller provides a more specific code.

## 8. ValidationError

ValidationError means:

> supplied domain/application input is invalid.

Default code:

~~~text
validation.error
~~~

## 9. NotFoundError

NotFoundError means:

> the requested domain resource does not exist.

Default code:

~~~text
resource.not_found
~~~

## 10. ConflictError

ConflictError means:

> the requested operation conflicts with current domain state.

Default code:

~~~text
resource.conflict
~~~

## 11. DuplicateError is a ConflictError

DuplicateError represents uniqueness/idempotency collisions.

Default code:

~~~text
resource.duplicate
~~~

Inheritance:

~~~text
DuplicateError
    ↓
ConflictError
    ↓
PyCRMKitError
~~~

## 12. InvalidStateError is also a ConflictError

InvalidStateError represents disallowed lifecycle/state transitions.

Default code:

~~~text
state.invalid
~~~

Inheritance:

~~~text
InvalidStateError
    ↓
ConflictError
    ↓
PyCRMKitError
~~~

## 13. RepositoryError

RepositoryError represents persistence adapter/repository failures.

Default code:

~~~text
repository.error
~~~

## 14. IntegrationError

IntegrationError represents an external provider/integration failure.

Default code:

~~~text
integration.error
~~~

## 15. The hierarchy is intentionally small

The stable public classes are:

~~~text
PyCRMKitError
├── ValidationError
├── NotFoundError
├── ConflictError
│   ├── DuplicateError
│   └── InvalidStateError
├── RepositoryError
└── IntegrationError
~~~

## 16. Precise behavior is usually expressed through codes

A domain may raise:

~~~text
ValidationError
code = contact.email.invalid
~~~

instead of introducing one Python subclass for every validation rule.

## 17. The same principle applies to repository failures

RepositoryError can carry:

~~~text
repository.foreign_key_violation
repository.not_null_violation
repository.check_violation
repository.serialization_failure
repository.deadlock
repository.backend_error
~~~

## 18. Stable code beats exception-message parsing

Do not branch on words in the human message.

Prefer the stable error.code value.

# Structured serialization

## 19. PyCRMKitError.as_dict returns the public shape

The result is:

~~~text
code
message
context
~~~

## 20. as_dict applies privacy redaction

The raw in-memory error context may contain sensitive values.

The public serialized representation is redacted.

## 21. Raw error.context is not automatically mutated

A sensitive value may remain in trusted in-process context while as_dict emits:

~~~text
[REDACTED]
~~~

for the corresponding sensitive key.

## 22. Redaction is recursive

Sensitive keys nested inside mappings are redacted as well.

## 23. Sensitive-key matching is normalized

Keys are trimmed, case-folded and hyphens are normalized to underscores.

## 24. Known sensitive keys include categories such as

~~~text
email
phone
address
password
token
secret
api_key
authorization
credentials
signing_secret
message_body
text_body
html_body
recipient
sender
body
external_id
idempotency_key
~~~

## 25. Suffix-based secret keys are also protected

A key ending with:

~~~text
_api_key
_password
_secret
_token
~~~

is treated as sensitive.

## 26. Safe keys remain visible

Example:

~~~text
contact_id
constraint
table
column
sqlstate
safe
~~~

may remain visible when not otherwise sensitive.

## 27. Redaction is key-based

The helper does not attempt arbitrary semantic inspection of every string.

Applications should therefore avoid putting secrets under misleadingly safe
keys.

## 28. Error messages must also avoid secret material

Redacting context does not sanitize arbitrary sensitive data embedded directly
into message text.

# Domain validation

## 29. Domain validation is not transport validation

A transport layer may accept a structurally valid request that later violates a
PyCRMKit business/value-object rule.

## 30. Domain validation raises ValidationError

Examples include:

~~~text
invalid email
invalid phone
blank required field
invalid state value
invalid event envelope
invalid context metadata
~~~

## 31. Domain validation uses domain-specific codes when available

Examples:

~~~text
contact.email.invalid
crm.causation_id.invalid
event.schema_version.invalid
event.envelope.invalid
audit.action.invalid
timeline.id.event_mismatch
~~~

## 32. Validation messages should not echo raw customer inputs

Security tests explicitly verify invalid email/phone input is not repeated in
public error context.

## 33. ValidationError remains a semantic 422 at HTTP adapters

FastAPI and DRF both map PyCRMKit ValidationError to:

~~~text
422 Unprocessable Entity
~~~

The difference appears only for framework request-validation failures.

# Not found

## 34. NotFoundError is a semantic resource miss

Examples include resource-specific not-found codes and event registry
definition misses.

## 35. Not-found behavior remains backend-neutral

Memory, SQLAlchemy and Django repositories should expose the same public
not-found semantics.

## 36. HTTP adapters map NotFoundError to 404

~~~text
NotFoundError -> 404
~~~

# Conflicts, duplicates and invalid state

## 37. ConflictError maps operation/state collisions

Examples include:

~~~text
duplicate identities
duplicate tags
already-completed lifecycle operation
ownership conflict
invalid transition
~~~

## 38. DuplicateError is specifically uniqueness/idempotency oriented

Examples:

~~~text
resource.duplicate
repository.duplicate
external_identity.duplicate
~~~

## 39. InvalidStateError is transition-oriented

It also represents transaction-lifecycle misuse where appropriate.

## 40. Conflict subclasses inherit HTTP 409 behavior

FastAPI and DRF map ConflictError and subclasses to:

~~~text
409 Conflict
~~~

## 41. DuplicateError therefore maps to 409

The precise body code still distinguishes uniqueness semantics.

## 42. InvalidStateError therefore maps to 409

A lifecycle conflict is not represented as generic 500.

## 43. Code remains more specific than status

The same HTTP 409 can carry different stable domain codes.

# Repository errors

## 44. Persistence internals must be translated

A database driver exception should not cross the public application boundary
unchanged.

## 45. SQLAlchemy adapter owns SQLAlchemy translation

The stable translation function is:

~~~text
translate_sqlalchemy_error
~~~

## 46. Translation output is a PyCRMKit error

The adapter returns DuplicateError or RepositoryError depending on the backend
condition.

## 47. PostgreSQL uniqueness violation

SQLSTATE:

~~~text
23505
~~~

maps to:

~~~text
DuplicateError
code = repository.duplicate
~~~

## 48. Foreign-key violation

SQLSTATE:

~~~text
23503
~~~

maps to:

~~~text
RepositoryError
code = repository.foreign_key_violation
~~~

## 49. NOT NULL violation

SQLSTATE:

~~~text
23502
~~~

maps to:

~~~text
repository.not_null_violation
~~~

## 50. CHECK violation

SQLSTATE:

~~~text
23514
~~~

maps to:

~~~text
repository.check_violation
~~~

## 51. Other IntegrityError cases

Unknown integrity failures map to:

~~~text
repository.integrity_error
~~~

## 52. Serialization failure

SQLSTATE:

~~~text
40001
~~~

maps to:

~~~text
repository.serialization_failure
~~~

## 53. Deadlock

SQLSTATE:

~~~text
40P01
~~~

maps to:

~~~text
repository.deadlock
~~~

## 54. Other SQLAlchemy failures

The fallback is:

~~~text
RepositoryError
code = repository.backend_error
~~~

## 55. SQLAlchemy context is deliberately narrow

Safe context may contain:

~~~text
sqlstate
constraint
table
column
~~~

## 56. SQL statement text is excluded

Translated context does not expose:

~~~text
statement
~~~

## 57. SQL parameter values are excluded

Translated context does not expose:

~~~text
params
~~~

## 58. Driver exception text is not copied wholesale

Translation builds a fresh stable public message and safe context.

## 59. This reduces customer-data leakage risk

SQL parameters may contain emails, names, tokens, payloads or other sensitive
values.

## 60. It also stabilizes adapter behavior

Application code sees PyCRMKit repository semantics rather than driver-specific
exception classes/messages.

## 61. Concurrent PostgreSQL duplicate behavior is qualified

Two transactions racing to persist normalized duplicate Tags produce:

~~~text
one commit
one DuplicateError
~~~

## 62. Duplicate translation preserves SQLSTATE

The qualified duplicate error context includes:

~~~text
sqlstate = 23505
~~~

## 63. Foreign-key qualification proves statement/params remain absent

This is a stable privacy boundary around persistence diagnostics.

# Transaction error handling

## 64. SQLAlchemy commit failure triggers rollback

The Unit of Work follows:

~~~text
Session.commit()
      X
Session.rollback()
clear pending events
translate / re-raise
~~~

## 65. Failed commit cannot publish staged events

Event publication occurs only after successful commit.

## 66. Django transaction failures are normalized separately

DjangoTransactionBridge uses stable codes for infrastructure failures.

## 67. Begin failure

~~~text
django.transaction.begin_failed
~~~

## 68. Commit failure

~~~text
django.transaction.commit_failed
~~~

## 69. Rollback failure

~~~text
django.transaction.rollback_failed
~~~

## 70. Invalid transaction lifecycle belongs to the conflict family

Examples include:

~~~text
django.transaction.not_active
django.transaction.already_committed
memory.uow.already_active
memory.uow.already_committed
sqlalchemy.uow.not_active
sqlalchemy.uow.already_committed
~~~

# Integration failures

## 71. IntegrationError represents external-system failure

Examples can include email providers, HTTP integrations or external delivery.

## 72. Integration failures are distinct from repository failures

~~~text
RepositoryError
= persistence boundary failed

IntegrationError
= external service/provider boundary failed
~~~

## 73. HTTP adapters map IntegrationError to 502

~~~text
IntegrationError -> 502 Bad Gateway
~~~

## 74. 502 communicates upstream dependency failure

The application handled the request but a required external integration failed.

## 75. Integration context follows the same privacy rules

Tokens, credentials, request bodies and secrets should not appear in public
error context.

# FastAPI error bridge

## 76. FastAPI uses ErrorResponse

The stable response model is:

~~~text
code
message
context
~~~

## 77. Extra fields are forbidden

ErrorResponse uses strict Pydantic extra-field behavior.

## 78. ErrorResponse.from_error applies redaction

Sensitive raw error context becomes safe public context.

## 79. FastAPI PyCRMKit status mapping

~~~text
ValidationError  -> 422
NotFoundError    -> 404
ConflictError    -> 409
RepositoryError  -> 500
IntegrationError -> 502
PyCRMKitError    -> 500
~~~

## 80. FastAPI request validation is a different failure family

FastAPI/Pydantic raises RequestValidationError before the domain call.

## 81. FastAPI request validation maps to 422

The stable envelope is:

~~~text
code    = request.validation_error
message = request validation failed
status  = 422
~~~

## 82. FastAPI validation context contains metadata only

Each detail contains:

~~~text
type
location
message
~~~

## 83. Submitted input is intentionally excluded

The handler does not copy raw request input into public context.

## 84. This avoids accidental PII/secret echo

Malformed values do not need to be reflected back in diagnostics.

## 85. install_error_handlers registers both bridges

It registers handlers for:

~~~text
PyCRMKitError
RequestValidationError
~~~

## 86. Unknown exceptions are not rewritten by the PyCRMKit handler

Framework/application fallback remains available for unrelated exceptions.

## 87. OpenAPI error documentation uses ErrorResponse

The integration advertises typed public errors for documented route statuses.

## 88. Documented status families include

~~~text
404
409
422
500
502
~~~

according to route capability.

# DRF error bridge

## 89. DRF also exposes code/message/context

The serializer contract mirrors the stable public shape.

## 90. DRF PyCRMKit mapping matches semantic families

~~~text
ValidationError  -> 422
NotFoundError    -> 404
ConflictError    -> 409
RepositoryError  -> 500
IntegrationError -> 502
PyCRMKitError    -> 500
~~~

## 91. DRF request validation differs from FastAPI

DRF's own ValidationError normally produces:

~~~text
400 Bad Request
~~~

## 92. DRF preserves 400 for request-shape validation

The normalized code is still:

~~~text
request.validation_error
~~~

## 93. Domain ValidationError remains 422

Therefore:

~~~text
DRF malformed transport request -> 400
PyCRMKit domain validation      -> 422
~~~

## 94. DRF validation details are flattened

Nested ErrorDetail structures become:

~~~text
code
location
message
~~~

## 95. Nested location is represented as path segments

Example:

~~~text
["email", "0"]
~~~

## 96. DRF also avoids submitted-input echo

The bridge serializes error metadata rather than request values.

## 97. DRF makes context JSON-safe

Unknown context objects are converted to strings after privacy redaction.

## 98. Unknown DRF exceptions delegate to the framework handler

The PyCRMKit handler intercepts public PyCRMKit errors and DRF validation
errors, then delegates everything else.

# Transport comparison

## 99. Domain error semantics are consistent

For PyCRMKit errors:

~~~text
Validation -> 422
NotFound   -> 404
Conflict   -> 409
Repository -> 500
Integration-> 502
~~~

across FastAPI and DRF.

## 100. Request-validation semantics differ by framework

~~~text
FastAPI request validation -> 422
DRF request validation     -> 400
~~~

## 101. This difference is intentional

PyCRMKit normalizes shape/privacy while respecting the framework's established
request-validation status behavior.

## 102. Client code should inspect code and status together

Transport validation and domain validation can therefore be distinguished
without parsing prose.

# Safe diagnostics

## 103. Public diagnostics should answer what failed

Useful safe metadata can include:

~~~text
entity ID
field name
constraint name
table name
column name
SQLSTATE
transition/state identifier
~~~

## 104. Public diagnostics should avoid sensitive values

Avoid:

~~~text
raw SQL params
passwords
tokens
authorization headers
raw request bodies
email content
phone values
webhook secrets
provider credentials
~~~

## 105. Sensitive diagnostics are recursively redacted by key

This is the built-in safety net.

## 106. The safety net is not a substitute for careful error design

Do not hide sensitive material under arbitrary safe-looking keys.

## 107. Stable messages should remain generic

A generic persistence constraint message is safer than raw driver text.

## 108. Backend exception repr should not become public API

Third-party message formats can change and may contain implementation detail.

# Designing domain/application errors

## 109. Choose the semantic family first

Ask whether the failure is:

~~~text
invalid input
missing resource
current-state conflict
persistence failure
external integration failure
~~~

## 110. Choose a stable code second

Good codes identify the exact public condition.

Examples:

~~~text
contact.not_found
task.transition.invalid
external_identity.owner.conflict
repository.deadlock
~~~

## 111. Keep codes stable across wording changes

Messages can improve without breaking client automation.

## 112. Keep context minimal

Expose only what helps a caller understand or recover.

## 113. Prefer identifiers over full object dumps

Expose a resource identifier rather than serializing an entire entity.

## 114. Prefer field names over raw field values

Field metadata is often enough to explain validation failure safely.

## 115. Avoid adapter-specific exceptions in facade code

Public callers should not need to catch SQLAlchemy, psycopg or Django database
exceptions.

## 116. Translate at the adapter boundary

Adapters understand implementation failures well enough to normalize them.

# Retry and recovery

## 117. Not every RepositoryError is equally retryable

Examples:

~~~text
repository.deadlock
repository.serialization_failure
~~~

may be transient.

By contrast:

~~~text
repository.not_null_violation
repository.check_violation
~~~

usually indicate a deterministic data/schema problem.

## 118. PyCRMKit does not silently retry all repository failures

Retry policy remains explicit unless a specific subsystem documents its own
retry behavior.

## 119. DuplicateError is not normally a transient infrastructure failure

It expresses a uniqueness conflict requiring semantic handling.

## 120. IntegrationError retry behavior is provider-specific

The broad class alone does not define universal retry policy.

## 121. Stable codes make explicit recovery policy possible

Applications can branch on codes rather than human message text.

# Testing error contracts

## 122. Exception hierarchy tests should cover

~~~text
default codes
inheritance
custom code override
message
raw context
as_dict
~~~

## 123. Privacy tests should cover recursive redaction

Include nested sensitive keys and safe sibling keys.

## 124. Domain validation tests should ensure raw customer data is not echoed

Examples include invalid email and phone values.

## 125. SQLAlchemy translation tests should cover

~~~text
23505 duplicate
23503 foreign key
23502 not null
23514 check
40001 serialization
40P01 deadlock
fallback backend error
~~~

## 126. SQLAlchemy privacy tests should assert absence of

~~~text
statement
params
~~~

## 127. PostgreSQL concurrency tests should verify duplicate races

One transaction commits and one surfaces repository.duplicate.

## 128. Transaction failure tests should verify event behavior

A failed commit must not publish pending events.

## 129. FastAPI error tests should cover

~~~text
ValidationError -> 422
NotFoundError -> 404
ConflictError -> 409
RepositoryError -> 500
IntegrationError -> 502
request validation -> 422
no input echo
~~~

## 130. DRF error tests should cover

~~~text
same PyCRMKit semantic mappings
request validation -> 400
flattened error paths
no input echo
~~~

## 131. Real-route tests should verify domain codes survive HTTP

Examples currently include:

~~~text
contact.not_found
task.transition.invalid
~~~

## 132. Security regression tests should verify public serialization redacts secrets

The stable suite already qualifies nested email/api_key/phone redaction.

# Common mistakes

### Catching Exception everywhere and returning 500

This destroys semantic error information.

### Creating one Python exception subclass for every code

The stable design combines a small semantic hierarchy with precise codes.

### Parsing error.message in client logic

Use error.code.

### Returning raw SQLAlchemy or psycopg exceptions

Translate them into PyCRMKit errors.

### Including SQL params in RepositoryError context

Those params may contain sensitive data.

### Including full SQL statements by default

Statements expose implementation detail and may expose sensitive values.

### Returning raw request-validation input

Only error metadata is required.

### Assuming FastAPI and DRF use the same request-validation status

FastAPI uses 422; DRF uses 400.

### Treating all 409 errors as the same failure

Inspect the stable code.

### Treating all RepositoryError values as retryable

Recovery depends on the precise code.

### Treating IntegrationError as a repository failure

Persistence and external-provider semantics are distinct.

### Putting secrets in error messages

Context redaction does not sanitize arbitrary message prose.

### Assuming raw error.context is already redacted

Public serialization/helpers apply redaction.

### Logging third-party exception repr blindly

External exception repr can include sensitive implementation detail.

## What you learned

You can now explain:

- the PyCRMKitError hierarchy;
- semantic class versus stable error code;
- structured error context;
- public as_dict serialization;
- recursive sensitive-key redaction;
- ValidationError, NotFoundError and ConflictError semantics;
- DuplicateError and InvalidStateError inheritance;
- RepositoryError and IntegrationError;
- SQLAlchemy/PostgreSQL error translation;
- SQLSTATE mappings;
- safe database diagnostic context;
- deliberate SQL statement/parameter exclusion;
- Django transaction error normalization;
- FastAPI public error mapping;
- DRF public error mapping;
- FastAPI 422 versus DRF 400 request validation;
- validation-error privacy;
- framework fallback for unknown exceptions;
- stable-code-driven client recovery.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter              ✅
23 SQLAlchemy                  ✅
24 PostgreSQL                  ✅
25 Migrations                  ✅
26 FastAPI                     ✅
27 Django                      ✅
28 Django REST Framework       ✅
29 Transactions & Unit of Work ✅
30 Context, Events & Audit     ✅
31 Error Handling              ✅
32 Security & Privacy          ← NEXT
~~~

The failure path can now be summarized as:

~~~text
failure
  |
  v
semantic PyCRMKitError
  |
  +--> stable code
  +--> message
  +--> safe context
  |
  v
transport / diagnostic boundary
  |
  v
predictable public contract
~~~

## Next

The next chapter is **32 - Security & Privacy**.

That final LEVEL 6 chapter consolidates:

~~~text
sensitive data
      |
      +--> validation
      +--> errors
      +--> logs
      +--> repr
      +--> webhook delivery
      +--> audit
      +--> persistence
      |
      v
privacy/security boundaries
~~~

The next learning question is:

> How does PyCRMKit prevent secrets, credentials, customer payloads and
> infrastructure details from leaking through repr, logs, error responses,
> audit records, webhooks or persistence diagnostics while still preserving
> enough metadata for safe operations and debugging?
