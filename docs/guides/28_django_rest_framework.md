# Django REST Framework

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 27 established the Django application, ORM, migration, transaction and
admin boundaries. Django REST Framework adds an optional HTTP transport on top
of the public CRM facade.

The stable architecture is:

~~~text
HTTP Request
      |
      v
DRF Serializer / ViewSet
      |
      v
request-scoped CRM facade
      |
      v
Domain / Application Services
      |
      v
Unit of Work / Repository Protocol
      |
      v
selected persistence adapter
~~~

For the Django/PostgreSQL reference application, the lower half becomes:

~~~text
CRM facade
    |
    v
DjangoTransactionBridge
    |
    v
Django repositories
    |
    v
Django ORM
    |
    v
PostgreSQL
~~~

The central rule is:

> DRF is a transport adapter. Serializers validate and convert HTTP data;
> ViewSets call the public CRM facade; neither layer turns Django ORM models into
> the domain API.

## What you will learn

You will learn to:

- install DRF independently from the plain Django adapter;
- understand the transport-only dependency direction;
- configure the application-owned CRM factory;
- understand the reusable SimpleRouter;
- inventory the stable Contact, Organization and Relationship routes;
- understand why the current router remains bounded to three aggregate families;
- convert serializer data into PyCRMKit domain inputs;
- preserve PATCH omitted-versus-null semantics;
- understand typed Relationship endpoints;
- understand response payload helpers;
- understand offset pagination;
- propagate actor and correlation context;
- understand stable domain-error mapping;
- distinguish DRF request validation from domain validation;
- understand privacy-safe validation errors;
- understand PUT exclusion and explicit lifecycle actions;
- understand Memory-backed DRF tests versus Django/PostgreSQL production E2E;
- understand clean-wheel DRF qualification;
- prepare for the dedicated Transactions & Unit of Work chapter.

## 1. DRF is a separate optional extra

Install it with:

~~~bash
pip install "pycrmkit[drf]"
~~~

The stable ranges are:

~~~text
Django >= 5.2, < 5.3
djangorestframework >= 3.18, < 3.19
~~~

## 2. The plain Django extra deliberately excludes DRF

This installation:

~~~bash
pip install "pycrmkit[django]"
~~~

does not install rest_framework.

The separation is executable-tested from the built wheel.

## 3. Core PyCRMKit remains DRF-free

Installing the base package does not require Django or DRF.

The dependency direction remains optional and outward-facing.

## 4. Importing the DRF bridge without DRF gives a clear error

The package guard raises a ModuleNotFoundError that points consumers to:

~~~bash
pip install "pycrmkit[drf]"
~~~

## 5. DRF remains transport-only

The architecture is:

~~~text
DRF
 |
 v
PyCRMKit transport adapter
 |
 v
CRM facade
 |
 v
Domain
~~~

not:

~~~text
Domain
 |
 v
rest_framework.Serializer
~~~

## 6. ViewSets do not call Django ORM models

The stable ViewSets do not use:

~~~text
ContactModel.objects
OrganizationModel.objects
RelationshipModel.objects
~~~

They resolve a CRM facade and call its public namespaces.

## 7. ViewSets do not call Django repositories directly

They also do not depend on:

~~~text
DjangoContactRepository
DjangoOrganizationRepository
DjangoRelationshipRepository
~~~

Persistence selection belongs to application composition.

## 8. The application owns CRM construction

Configure:

~~~text
PYCRMKIT_CRM_FACTORY
~~~

with either a callable or a dotted import path.

## 9. A dotted path is resolved lazily

Example:

~~~python
PYCRMKIT_CRM_FACTORY = "project.crm.get_crm"
~~~

The bridge resolves it through Django import_string.

## 10. A callable can be configured directly

For tests:

~~~python
PYCRMKIT_CRM_FACTORY = lambda: crm
~~~

This makes Memory-backed HTTP tests easy.

## 11. Missing CRM factory is a configuration error

If PYCRMKIT_CRM_FACTORY is absent, get_crm_factory raises Django
ImproperlyConfigured.

## 12. Non-callable CRM factory is rejected

The setting must resolve to a callable returning a CRM.

## 13. One reusable router factory defines the stable surface

~~~python
from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()
~~~

It returns a DRF SimpleRouter.

## 14. Mount the router through Django URLs

~~~python
from django.urls import include, path

urlpatterns = [
    path("crm/", include(router.urls)),
]
~~~

## 15. The stable router contains three ViewSets

The current factory registers:

~~~text
contacts
organizations
relationships
~~~

## 16. External Identities are not in the reusable DRF router

Chapter 27 showed that Django persistence now includes External Identity.

The current reusable DRF router still does not expose an External Identity
ViewSet.

## 17. HTTP scope and persistence scope are not identical

Current V1:

~~~text
Django persistence
├── Contacts
├── Organizations
├── Relationships
└── External Identities

DRF router
├── Contacts
├── Organizations
└── Relationships
~~~

Do not infer an HTTP endpoint merely because a repository exists.

## 18. Contact routes

~~~text
GET    /contacts/
POST   /contacts/
GET    /contacts/{id}/
PATCH  /contacts/{id}/
POST   /contacts/{id}/archive/
~~~

## 19. Organization routes

~~~text
GET    /organizations/
POST   /organizations/
GET    /organizations/{id}/
PATCH  /organizations/{id}/
POST   /organizations/{id}/archive/
~~~

## 20. Relationship routes

~~~text
GET    /relationships/
POST   /relationships/
GET    /relationships/{id}/
PATCH  /relationships/{id}/
POST   /relationships/{id}/end/
~~~

## 21. Full PUT replacement is intentionally absent

The stable helper surface does not expose PUT.

PyCRMKit domain update APIs use explicit partial-update DTO semantics.

## 22. PUT returns method-not-allowed

The integration tests verify Contact PUT receives:

~~~text
405 Method Not Allowed
~~~

## 23. Lifecycle commands remain explicit actions

Archive and end are represented as DRF actions rather than generic DELETE.

## 24. Serializer classes are transport schemas

The public bridge includes create, update and response serializers for Contact,
Organization and Relationship.

These serializers are not domain entities.

## 25. Nested serializer helpers model transport shape

Contact uses email, phone and address serializers.

Organization uses domain and address serializers.

Relationship uses RelationshipEndpointSerializer.

## 26. Serializer validation handles HTTP shape and basic types

DRF validates UUID syntax, string bounds, choices, required fields, nullability,
pagination integers and nested object structure.

## 27. Domain constructors remain authoritative for normalization

After serializer validation the bridge constructs PyCRMKit value objects such
as ContactEmail, ContactPhone, Address, OrganizationDomain,
OrganizationAddress, RelationshipType and RelationshipEndpoint.

## 28. Contact create conversion is explicit

~~~text
request.data
      |
      v
ContactCreateSerializer
      |
      v
validated_data
      |
      v
to_domain_kwargs()
      |
      v
crm.contacts.create(...)
~~~

## 29. Email normalization remains domain-owned

An input such as:

~~~text
ADA@Example.COM
~~~

is passed into ContactEmail and normalized by the domain value object.

## 30. Phone normalization remains domain-owned

ContactPhone owns its comparison normalization rather than DRF.

## 31. Address normalization remains domain-owned

Address construction owns country-code normalization.

## 32. Contact owner UUID becomes EntityId

UUIDField validates the transport value; the bridge reconstructs the typed
PyCRMKit EntityId.

## 33. Contact status becomes ContactStatus

Choice validation occurs at the transport layer, then ContactStatus is
constructed before the facade call.

## 34. Organization conversion is equally explicit

Organization serializers reconstruct OrganizationStatus, EntityId,
OrganizationDomain and OrganizationAddress values.

## 35. Relationship endpoints become typed domain references

A transport endpoint contains:

~~~text
kind
id
~~~

## 36. contact kind restores ContactId

The bridge creates a RelationshipEndpoint.contact around a typed ContactId.

## 37. organization kind restores OrganizationId

The bridge creates a RelationshipEndpoint.organization around a typed
OrganizationId.

## 38. RelationshipType normalization stays in the domain

A transport input such as employee_of can become the canonical employee-of form
through RelationshipType construction.

## 39. Response serialization is explicit

Domain entities first become controlled plain mappings through:

~~~text
contact_payload
organization_payload
relationship_payload
~~~

Response serializers then serialize those mappings.

## 40. Domain objects are not exposed blindly

The adapter controls public HTTP fields explicitly instead of dumping arbitrary
entity attributes.

## 41. PATCH requires three states

~~~text
field omitted
field explicitly null
field explicitly set
~~~

Those states are semantically different.

## 42. DRF preserves omission through validated_data membership

Unlike the FastAPI adapter's model_fields_set technique, DRF update serializers
check whether a key exists in validated_data.

## 43. Omitted Contact fields become CONTACT_UNSET

Example:

~~~text
PATCH {"first_name": null}

first_name -> None
last_name  -> UNSET
owner_id   -> UNSET
~~~

## 44. Explicit null clears nullable fields

Nullable Contact fields can be explicitly cleared when allowed by the domain.

## 45. Non-nullable Contact fields reject null

status, nested collections and metadata reject null.

## 46. Empty collections remain explicit replacements

~~~json
{
  "emails": []
}
~~~

replaces the email collection with empty rather than behaving like omission.

## 47. Empty metadata remains explicit

An empty metadata mapping is not converted to UNSET.

## 48. Organization PATCH follows the same pattern

Omitted fields become ORGANIZATION_UNSET; nullable fields such as trading_name
can be explicitly cleared.

## 49. Organization legal_name cannot be null

It may be omitted in PATCH, but explicit null is rejected.

## 50. Organization status cannot be null

It follows the same omission-versus-null distinction.

## 51. Relationship PATCH uses RELATIONSHIP_UNSET

Missing update keys preserve no-mutation semantics.

## 52. Relationship endpoints cannot be null

source and target may be omitted, but if present must be valid endpoint objects.

## 53. RelationshipType cannot be null

It may be omitted but not explicitly cleared.

## 54. Relationship role and title may be cleared

Those fields support explicit null.

## 55. valid_from cannot be explicitly null

It can be omitted; if provided it must be a datetime.

## 56. Ending a Relationship remains a separate action

The stable update serializer does not turn valid_until into a generic lifecycle
mutation. The end action calls crm.relationships.end.

## 57. CRMViewSet resolves a CRM per request

The base class calls:

~~~text
get_crm_factory()()
~~~

inside get_crm(request).

## 58. Request context supports two headers

~~~text
X-Actor-ID
X-Correlation-ID
~~~

## 59. No headers preserve the base CRM

If neither header is present, the base facade is returned unchanged.

## 60. One header preserves the other context value

The missing value comes from the base CRM context.

## 61. Both headers produce a contextual facade

The bridge calls CRM.with_context rather than mutating domain state.

## 62. Request context reaches Domain Events

The integration tests verify contact.created receives the actor and correlation
values supplied by HTTP headers.

## 63. DRF does not invent authentication policy

It only propagates request metadata. Authentication and authorization remain
application concerns.

## 64. Pagination bridges to OffsetPageRequest

PaginationQuerySerializer validates limit and offset, then to_domain returns the
framework-neutral OffsetPageRequest.

## 65. Pagination defaults come from the core contract

The default limit and maximum limit are taken from OffsetPageRequest constants.

## 66. Stable bounds

~~~text
limit >= 1
limit <= core maximum
offset >= 0
~~~

## 67. Invalid pagination is a request-validation error

For example, limit=0 is normalized through the DRF error bridge.

## 68. Page response shape is adapter-consistent

~~~text
items
limit
offset
total
has_next
has_previous
~~~

## 69. Page metadata comes from the core Page object

DRF does not independently recalculate pagination state.

## 70. Domain errors preserve stable public codes

The envelope is:

~~~text
code
message
context
~~~

## 71. Domain-error status mapping

~~~text
ValidationError  -> 422
NotFoundError    -> 404
ConflictError    -> 409
RepositoryError  -> 500
IntegrationError -> 502
PyCRMKitError    -> 500
~~~

## 72. Conflict subclasses retain 409 semantics

Duplicate and invalid-state errors inherit the public conflict hierarchy where
applicable.

## 73. Error context is privacy-filtered

The bridge applies PyCRMKit sensitive-mapping redaction before returning public
context.

## 74. Context values become JSON-safe

Nested mappings and sequences are traversed; unknown values fall back to string
representation.

## 75. DRF request validation is a separate family

DRF ValidationError becomes:

~~~text
code = request.validation_error
message = request validation failed
~~~

## 76. DRF request validation uses HTTP 400

This is an important difference from the FastAPI adapter.

Current DRF request-shape validation returns:

~~~text
400 Bad Request
~~~

## 77. Domain ValidationError still maps to 422

Therefore:

~~~text
malformed transport request -> 400
domain/business validation  -> 422
~~~

## 78. Validation details are flattened

Nested DRF ErrorDetail structures become entries with:

~~~text
code
location
message
~~~

## 79. Location is a path list

Example:

~~~json
{
  "code": "invalid",
  "location": ["status", "0"],
  "message": "..."
}
~~~

## 80. Submitted input is not echoed

The normalized error context carries error metadata but does not copy request
values.

## 81. Invalid route UUID is normalized

A non-UUID path parameter produces the same request.validation_error envelope.

## 82. Missing route ID is normalized too

The internal UUID helper treats missing resource IDs as request validation.

## 83. Packaged ViewSets handle public errors directly

CRMViewSet.handle_exception invokes the PyCRMKit error bridge for PyCRMKitError
and DRFValidationError.

## 84. Application-owned views can install the global handler

~~~python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "pycrmkit.integrations.django.drf.errors."
        "pycrmkit_exception_handler"
    ),
}
~~~

## 85. Unknown exceptions fall back to DRF

Unrecognized exceptions delegate to DRF's standard exception handler.

## 86. Contact ViewSet stays facade-backed

It calls only the public contacts namespace for search, create, get, update and
archive.

## 87. Organization ViewSet stays facade-backed

It calls only the public organizations namespace.

## 88. Relationship ViewSet stays facade-backed

It calls search, create, get, update and end on the public relationships
namespace.

## 89. Memory-backed API tests isolate transport semantics

The dedicated DRF tests use CRM.memory and FixedClock.

This keeps serializer, router, context and error behavior fast and deterministic.

## 90. DRF is not inherently tied to Django ORM persistence

The transport tests use a minimal Django configuration and Memory CRM.

That proves DRF sits over the facade rather than over Model objects.

## 91. Production reference wiring chooses Django persistence

The example Django project configures PYCRMKIT_CRM_FACTORY to return its
application-owned CRM wired to DjangoTransactionBridge.

## 92. Production path becomes DRF to Django bridge

~~~text
HTTP / DRF
      |
      v
CRM facade
      |
      v
DjangoTransactionBridge
      |
      v
Django repository
      |
      v
Django ORM
      |
      v
PostgreSQL 17
~~~

## 93. Reference URLs use the same router factory

The example mounts create_drf_router under /crm/.

## 94. PostgreSQL E2E creates Contact through DRF

The seed process POSTs Contact with actor and correlation headers.

## 95. PostgreSQL E2E creates Organization through DRF

The same HTTP journey creates the Organization.

## 96. PostgreSQL E2E creates Relationship through DRF

The Relationship payload contains typed Contact and Organization endpoints.

## 97. External Identity is attached through the CRM facade

This accurately demonstrates the current boundary: Django persistence supports
External Identity, but the reusable DRF router does not.

## 98. Fresh process reload proves durability

The verify process starts a new Python/Django process and GETs persisted
Contact, Organization and Relationship state through DRF.

## 99. PATCH after restart proves durable mutation

The fresh process updates the persisted Contact.

## 100. Relationship end after restart proves action semantics

The fresh process calls the end action and verifies the persisted lifecycle
change.

## 101. PostgreSQL-backed pagination is exercised

The E2E lists Contacts with limit/offset and checks total and returned identity.

## 102. The same journey is repeated from the built wheel

CI resets PostgreSQL, installs wheel[django,drf,postgresql], applies packaged
Django migrations and reruns the two-process E2E.

## 103. Dedicated DRF CI also qualifies the wheel

The DRF workflow installs wheel[drf] in a clean environment and runs a
Memory-backed facade smoke.

## 104. Installed-wheel smoke proves router packaging

The clean environment imports create_drf_router and successfully POSTs a
Contact.

## 105. Django-only installation remains DRF-free

The Django integration gate installs wheel[django] and verifies rest_framework
is absent.

## 106. Core-only installation remains Django/DRF-free

The production Django E2E separately verifies the base wheel does not pull in
either framework.

## 107. The stable DRF surface is intentionally narrow

Current reusable router:

~~~text
Contacts
Organizations
Relationships
~~~

It does not claim full HTTP coverage of all PyCRMKit modules.

## 108. Transport capability should follow facade capability

A new endpoint should call a stable CRM namespace, not bypass the facade to
manufacture behavior from internal repositories.

## 109. DRF serialization is not persistence serialization

Serializer payloads exist for HTTP interoperability.

Django models exist for storage.

Domain entities exist for business behavior.

## 110. Three-model mental map

~~~text
HTTP representation
  DRF Serializer
        |
        v
Domain representation
  PyCRMKit Entity / Value Object
        |
        v
Persistence representation
  Django ORM Model
~~~

## 111. Minimal settings

~~~python
PYCRMKIT_CRM_FACTORY = "project.crm.get_crm"

REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "pycrmkit.integrations.django.drf.errors."
        "pycrmkit_exception_handler"
    ),
}
~~~

## 112. Minimal URL configuration

~~~python
from django.urls import include, path
from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()

urlpatterns = [
    path("crm/", include(router.urls)),
]
~~~

## 113. Minimal Memory-backed factory

~~~python
from pycrmkit import CRM

crm = CRM.memory()

def get_crm() -> CRM:
    return crm
~~~

## 114. Production factory remains application-owned

The Django reference project constructs its CRM with DjangoTransactionBridge in
its composition module and exposes the factory through Django settings.

The ViewSets remain unchanged.

## Common mistakes

### Using ModelSerializer over PyCRMKit ORM models as the domain API

The stable bridge uses explicit Serializer classes and calls the CRM facade.

### Calling Model.objects from a ViewSet

ViewSets should stay facade-backed.

### Returning Django model instances from responses

Response serializers consume explicit domain payload mappings.

### Assuming the DRF router exposes External Identities

It currently exposes only Contacts, Organizations and Relationships.

### Assuming every PyCRMKit domain has a ViewSet

The stable HTTP surface is deliberately bounded.

### Treating serializer validation as domain validation

Transport validation and domain validation are distinct.

### Mapping DRF request validation to 422 by analogy with FastAPI

Current DRF request validation returns HTTP 400.

### Losing PATCH omission semantics

Missing fields must become domain UNSET, not None.

### Using PUT for partial domain updates

The reusable router intentionally does not expose PUT.

### Replacing archive/end with DELETE

Those are domain lifecycle actions.

### Echoing request values in validation errors

The normalized bridge deliberately avoids submitted input.

### Hard-coding persistence inside ViewSets

The application-owned CRM factory selects persistence.

### Forgetting PYCRMKIT_CRM_FACTORY

The integration requires an application-owned CRM factory.

### Installing Django and assuming DRF is present

The extras are intentionally separated.

### Testing only with Memory

Production qualification also runs DRF over Django ORM and PostgreSQL 17 across
fresh Python processes.

## Testing DRF integration

Serializer tests should cover:

~~~text
nested values
typed IDs
enum conversion
normalization through domain values
PATCH omitted versus null
non-nullable rejection
response payload shape
~~~

Router tests should cover:

~~~text
list
create
retrieve
PATCH
archive action
end action
PUT -> 405
~~~

Context tests should cover:

~~~text
X-Actor-ID
X-Correlation-ID
base context preservation
Domain Event metadata
~~~

Pagination tests should cover:

~~~text
default limit
bounded limit
non-negative offset
Page metadata
invalid query -> request.validation_error
~~~

Error tests should cover:

~~~text
ValidationError -> 422
NotFoundError -> 404
ConflictError -> 409
RepositoryError -> 500
IntegrationError -> 502
DRFValidationError -> 400
safe context
flattened validation details
no request-input echo
~~~

Dependency-boundary tests should cover:

~~~text
base wheel -> no Django/DRF
django extra -> no DRF
drf extra -> DRF available
missing DRF guard
~~~

Production E2E should cover:

~~~text
Django migrations
PostgreSQL 17
DRF Contact / Organization / Relationship
request context
pagination
fresh Python process
reload
PATCH
Relationship end
installed-wheel replay
~~~

## What you learned

You can now explain:

- why DRF is a separate optional transport;
- PYCRMKIT_CRM_FACTORY;
- callable and dotted factory resolution;
- the SimpleRouter surface;
- why DRF currently exposes only three aggregate families;
- serializer-to-domain conversion;
- explicit response payload mapping;
- typed Relationship endpoints;
- PATCH UNSET/null/value semantics;
- offset pagination;
- actor/correlation context propagation;
- domain error status mapping;
- DRF request validation as HTTP 400;
- validation privacy;
- action-oriented archive/end routes;
- Memory transport testing versus PostgreSQL production qualification;
- clean-wheel DRF packaging qualification.

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
29 Transactions & Unit of Work ← NEXT
30 Context, Events & Audit
31 Error Handling
32 Security & Privacy
~~~

The HTTP integration picture is now:

~~~text
FastAPI
   |
   v
CRM facade

DRF
   |
   v
CRM facade
~~~

Both transports remain outside the domain and can be composed with the
application-selected persistence strategy.

## Next

The next chapter is **29 - Transactions & Unit of Work**.

The next architecture unifies transaction semantics already encountered in
Memory, SQLAlchemy and Django:

~~~text
Application command
      |
      v
Unit of Work / Transaction boundary
      |
      +--> repository writes
      +--> rollback behavior
      +--> pending Domain Events
      |
      v
COMMIT
      |
      v
post-commit effects
~~~

The next learning question is:

> Which transaction semantics are portable across Memory, SQLAlchemy and Django,
> and where must PyCRMKit deliberately acknowledge adapter-specific behavior
> such as snapshots, SQL Sessions, Django savepoints and outer transaction
> ownership?
