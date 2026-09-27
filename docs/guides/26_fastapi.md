# FastAPI

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapters 22 through 25 built the persistence path:

~~~text
Domain
  |
  v
Repository contracts
  |
  v
SQLAlchemy
  |
  v
PostgreSQL
  |
  v
Alembic
~~~

This chapter moves upward from infrastructure to HTTP integration.

PyCRMKit provides an optional FastAPI adapter that exposes the stable CRM facade
without moving FastAPI, Pydantic, HTTP or OpenAPI concerns into the domain.

The stable architecture is:

~~~text
HTTP Request
     |
     v
FastAPI Router
     |
     v
Pydantic transport schema
     |
     v
CRMDependency
     |
     v
CRM facade
     |
     v
Domain / Application Services
     |
     v
Repository contracts
     |
     v
Persistence adapter
~~~

The central rule is:

> FastAPI is an integration adapter around the CRM facade. Routers do not reach
> through the facade to SQLAlchemy Sessions, ORM models or repository
> implementations.

## What you will learn

You will learn to:

- install the optional FastAPI integration;
- understand the framework boundary;
- compose the reusable CRM router;
- understand request-scoped CRM context;
- map Pydantic request models into domain inputs;
- map domain entities into response models;
- preserve PATCH omitted-versus-null semantics;
- understand router coverage and command-oriented endpoints;
- use the pagination bridge;
- understand the stable ErrorResponse contract;
- understand PyCRMKit error to HTTP status mapping;
- understand request-validation normalization;
- understand OpenAPI qualification;
- wire the same HTTP layer to Memory or PostgreSQL;
- understand migration-first application startup;
- understand the PostgreSQL-backed API E2E and restart test.

## 1. FastAPI support is optional

Install it with:

~~~bash
pip install "pycrmkit[fastapi]"
~~~

The stable dependency range is:

~~~text
fastapi >= 0.141, < 0.142
pydantic >= 2.13, < 2.14
~~~

The core package has no mandatory FastAPI dependency.

## 2. Core import remains framework-independent

A minimal installation can still do:

~~~python
import pycrmkit
~~~

without importing FastAPI transitively.

This optional-dependency boundary is explicitly tested.

## 3. FastAPI lives in an integration package

The integration surface lives under:

~~~text
pycrmkit.integrations.fastapi
~~~

The stable package contains:

~~~text
dependencies.py
schemas.py
errors.py
pagination.py
router.py
routers/
    contacts.py
    organizations.py
    relationships.py
    activities.py
    tasks.py
    leads.py
    opportunities.py
    timeline.py
~~~

## 4. The domain does not import FastAPI

Dependency direction remains one-way:

~~~text
FastAPI / Pydantic
       |
       v
PyCRMKit integration layer
       |
       v
CRM facade
       |
       v
Domain
~~~

The domain does not depend on FastAPI or Pydantic.

## 5. The consuming application owns CRM construction

The reusable router accepts a CRM factory.

The application decides whether that CRM uses:

~~~text
Memory
SQLAlchemy
PostgreSQL
custom adapters
~~~

The router does not make that choice.

## 6. Minimal Memory-backed application

~~~python
from fastapi import FastAPI

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import (
    create_crm_router,
    install_error_handlers,
)

crm = CRM.memory()

app = FastAPI()
install_error_handlers(app)
app.include_router(
    create_crm_router(lambda: crm),
    prefix="/crm",
)
~~~

The same route code can later use PostgreSQL-backed CRM wiring.

## 7. create_crm_router is the composite router factory

The public helper:

~~~text
create_crm_router(factory)
~~~

builds a reusable APIRouter that includes all stable FastAPI CRM surfaces.

## 8. The composite router includes eight areas

It includes routers for:

~~~text
Contacts
Organizations
Relationships
Activities
Tasks
Leads
Opportunities
Timeline
~~~

## 9. Routers receive a CRMDependency

create_crm_router constructs one CRMDependency around the supplied factory.

That dependency is then passed to each sub-router.

## 10. Routers use the public CRM facade

A Contact endpoint calls:

~~~text
crm.contacts.create
crm.contacts.search
crm.contacts.get
crm.contacts.update
crm.contacts.archive
~~~

It does not access:

~~~text
SQLAlchemy Session
ContactModel
ContactRepository implementation
CRM._runtime
~~~

## 11. The request path stays facade-first

For a Contact creation:

~~~text
POST /crm/contacts
       |
       v
ContactCreateRequest
       |
       v
to_domain_kwargs
       |
       v
crm.contacts.create(...)
       |
       v
Contact
       |
       v
ContactResponse.from_domain(...)
       |
       v
JSON response
~~~

## 12. Pydantic models are transport objects

ContactCreateRequest is not a domain Entity.

ContactResponse is not a domain Entity.

They represent the HTTP boundary.

## 13. Transport schemas inherit from APIModel

The integration uses a strict Pydantic base:

~~~text
APIModel
  |
  +--> extra = forbid
~~~

Unexpected request fields are therefore rejected rather than silently accepted.

## 14. Request schemas explicitly convert to domain inputs

For example:

~~~python
request = ContactCreateRequest(
    first_name="Ada",
    last_name="Lovelace",
)

contact = crm.contacts.create(
    **request.to_domain_kwargs()
)
~~~

The conversion boundary is explicit.

## 15. Response schemas explicitly convert from domain entities

~~~python
response = ContactResponse.from_domain(contact)
~~~

The router returns a transport representation rather than returning the domain
object directly.

## 16. UUID transport values become typed domain IDs

Transport schemas commonly accept UUID values.

Conversion reconstructs domain types such as:

~~~text
ContactId
OrganizationId
ActivityId
TaskId
LeadId
OpportunityId
TimelineEntryId
EntityId
~~~

## 17. EntityReferenceSchema preserves typed references

EntityReferenceSchema accepts:

~~~text
kind
id
~~~

and maps known kinds to the corresponding typed UUID ID classes.

For unknown supported generic kinds it falls back to the generic UUIDId type.

## 18. Value objects remain domain-owned

ContactEmailSchema converts to ContactEmail.

ContactPhoneSchema converts to ContactPhone.

AddressSchema converts to Address.

Pydantic validates the transport shape, while domain constructors retain
business normalization and validation behavior.

## 19. Normalization remains a domain concern

For example, the API may receive:

~~~text
Ada@Example.COM
~~~

The transport schema passes the value into ContactEmail.

The domain value object is responsible for normalized email semantics.

## 20. Response serialization can preserve submitted form and domain meaning

A Contact response can expose the stored display value while the domain still
maintains a normalized representation for search and equality rules.

Transport and domain concerns remain separate.

## 21. PATCH semantics require more than Optional fields

A PATCH request must distinguish:

~~~text
field omitted
field explicitly null
field explicitly set to a value
~~~

Those three states are not equivalent.

## 22. Pydantic model_fields_set preserves omission

ContactUpdateRequest uses model_fields_set to determine which properties were
actually present in the request.

This is how the transport layer preserves domain UNSET semantics.

## 23. Omitted field becomes domain UNSET

Example:

~~~python
patch = ContactUpdateRequest(display_name=None)

update = patch.to_domain()
~~~

For a field not supplied, the domain update receives the appropriate UNSET
sentinel rather than None.

## 24. Explicit null remains an explicit clear where allowed

If display_name is explicitly provided as null, the transport conversion can
produce:

~~~text
display_name = None
~~~

rather than UNSET.

That tells the domain to clear the field.

## 25. Explicit empty metadata remains explicit replacement

A PATCH payload containing:

~~~json
{
  "metadata": {}
}
~~~

maps to an empty dictionary, not UNSET.

## 26. Non-nullable update fields reject explicit null

The integration adds model validators for fields that may be omitted but cannot
be explicitly cleared.

For ContactUpdateRequest:

~~~text
status = null
~~~

is rejected.

For OrganizationUpdateRequest, legal_name and status cannot be explicitly null.

## 27. HTTP validation and domain validation are separate layers

Pydantic can reject malformed transport data before the CRM facade is called.

Domain code can still reject semantically invalid CRM data after transport
validation succeeds.

Both failures use the stable HTTP error envelope once handlers are installed.

## 28. CRMDependency constructs a request-scoped facade view

CRMDependency accepts a CRM factory:

~~~text
Callable[[], CRM]
~~~

Every dependency invocation calls that factory.

## 29. CRMDependency understands two HTTP headers

The stable request metadata headers are:

~~~text
X-Actor-ID
X-Correlation-ID
~~~

Both accept optional string values with a maximum length of 255.

## 30. Missing headers preserve the base context

If neither header is supplied, CRMDependency returns the base CRM produced by
the factory without changing its context.

## 31. Supplying only one header preserves the other base value

If only X-Actor-ID is supplied:

~~~text
actor_id       = HTTP value
correlation_id = base CRM context
~~~

If only X-Correlation-ID is supplied, actor_id is preserved.

## 32. Supplying both creates a contextual CRM view

CRMDependency calls:

~~~text
CRM.with_context(...)
~~~

It does not mutate domain objects manually.

## 33. Request context can flow into audit and events

Because request metadata is applied through the stable CRM context API, domain
operations executed through the facade can inherit actor and correlation
metadata using the same mechanisms as non-HTTP applications.

## 34. Header transport remains outside the domain

The domain does not know the header names:

~~~text
X-Actor-ID
X-Correlation-ID
~~~

Only the FastAPI integration understands those HTTP details.

## 35. Contacts expose a CRUD-plus-command surface

The stable Contact router provides:

~~~text
POST   /contacts
GET    /contacts
GET    /contacts/{contact_id}
PATCH  /contacts/{contact_id}
POST   /contacts/{contact_id}/archive
~~~

## 36. Organization routes mirror the public facade

~~~text
POST   /organizations
GET    /organizations
GET    /organizations/{organization_id}
PATCH  /organizations/{organization_id}
POST   /organizations/{organization_id}/archive
~~~

## 37. Relationship lifecycle stays explicit

~~~text
POST   /relationships
GET    /relationships
GET    /relationships/{relationship_id}
PATCH  /relationships/{relationship_id}
POST   /relationships/{relationship_id}/end
~~~

Ending a relationship is not represented as a generic DELETE.

## 38. Activities expose log/read/update semantics

~~~text
POST   /activities
GET    /activities
GET    /activities/{activity_id}
PATCH  /activities/{activity_id}
~~~

POST maps to crm.activities.log.

## 39. Tasks expose domain commands

~~~text
POST   /tasks
GET    /tasks
GET    /tasks/{task_id}
PATCH  /tasks/{task_id}

POST   /tasks/{task_id}/start
POST   /tasks/{task_id}/complete
POST   /tasks/{task_id}/cancel
POST   /tasks/{task_id}/reopen
~~~

State transitions are explicit HTTP commands.

## 40. Leads are intentionally command-oriented

The stable Lead router exposes:

~~~text
POST /leads
POST /leads/{lead_id}/qualify
POST /leads/{lead_id}/disqualify
POST /leads/{lead_id}/convert
~~~

It does not invent GET endpoints that are absent from the public Lead facade.

## 41. Opportunities are also command-oriented

The stable Opportunity router exposes:

~~~text
POST /opportunities
POST /opportunities/{opportunity_id}/move
~~~

Again, it does not reach into repositories to manufacture a broader HTTP API.

## 42. Lead conversion returns an OpportunityResponse

~~~text
POST /leads/{lead_id}/convert
        |
        v
LeadConversionRequest
        |
        v
crm.leads.convert(...)
        |
        v
Opportunity
        |
        v
OpportunityResponse
~~~

## 43. Opportunity movement remains a domain command

~~~text
POST /opportunities/{opportunity_id}/move
~~~

accepts OpportunityMoveRequest and calls:

~~~text
crm.opportunities.move(...)
~~~

## 44. Timeline remains read-only

Timeline routes are:

~~~text
GET /timeline/entries/{entry_id}
GET /timeline/contacts/{contact_id}
GET /timeline/organizations/{organization_id}
~~~

There are no generic mutation endpoints for Timeline projections.

## 45. HTTP surface follows domain shape, not generic CRUD ideology

The integration deliberately exposes domain commands where the facade is
command-oriented.

This preserves the domain language at the HTTP boundary.

## 46. Pagination has its own transport bridge

The path is:

~~~text
HTTP query parameters
       |
       v
PaginationParams
       |
       v
OffsetPageRequest
       |
       v
CRM facade
       |
       v
Page[T]
       |
       v
PageResponse[T]
~~~

## 47. Stable pagination defaults match the core contract

~~~text
default limit = 50
maximum limit = 200
minimum limit = 1
offset >= 0
~~~

## 48. Invalid HTTP pagination is rejected by FastAPI/Pydantic

For example:

~~~text
?limit=201
~~~

produces HTTP 422.

## 49. PageResponse preserves exact pagination metadata

It serializes:

~~~text
items
limit
offset
total
has_next
has_previous
~~~

## 50. PageResponse maps domain items explicitly

PageResponse.from_page accepts a mapper for each item.

This prevents generic domain objects from being dumped directly as arbitrary
JSON.

## 51. FastAPI error mapping is opt-in at application setup

The application should explicitly call:

~~~python
install_error_handlers(app)
~~~

This registers handlers for:

~~~text
PyCRMKitError
RequestValidationError
~~~

## 52. ErrorResponse is the stable HTTP envelope

Mapped errors use:

~~~json
{
  "code": "resource.not_found",
  "message": "resource not found",
  "context": {}
}
~~~

The fields are:

~~~text
code
message
context
~~~

## 53. Stable domain-error status mapping

The mapping is:

~~~text
ValidationError       -> 422
NotFoundError         -> 404
ConflictError         -> 409
DuplicateError        -> 409
InvalidStateError     -> 409
RepositoryError       -> 500
IntegrationError      -> 502
PyCRMKitError         -> 500
~~~

DuplicateError and InvalidStateError inherit through the public error hierarchy
and therefore map to conflict semantics.

## 54. status_code_for_error exposes the mapping directly

Applications can call:

~~~text
status_code_for_error(error)
~~~

when they need the mapping independently from the installed exception handler.

## 55. Error context is privacy-filtered

ErrorResponse.from_error applies the package privacy redaction helper before
serializing the public context mapping.

Transport error handling therefore preserves stable codes without blindly
echoing arbitrary sensitive context.

## 56. FastAPI request validation uses the same envelope

RequestValidationError becomes:

~~~json
{
  "code": "request.validation_error",
  "message": "request validation failed",
  "context": {
    "errors": []
  }
}
~~~

## 57. Request-validation details are bounded

Each validation detail exposes:

~~~text
type
location
message
~~~

## 58. Submitted input is deliberately omitted

The validation normalizer does not include FastAPI/Pydantic input echo in the
generic ErrorResponse context.

This is explicitly tested.

## 59. Domain validation and request validation remain distinguishable

A Pydantic/FastAPI validation failure has:

~~~text
code = request.validation_error
~~~

A domain ValidationError preserves its own PyCRMKit error code.

Both use status 422 and the same envelope shape.

## 60. Not-found behavior is preserved through real routes

A missing Contact reached through:

~~~text
GET /contacts/{id}
~~~

becomes:

~~~text
404
code = contact.not_found
~~~

## 61. Invalid state becomes HTTP conflict

For example, completing an already completed Task raises the domain transition
error and maps to:

~~~text
409
code = task.transition.invalid
~~~

## 62. Repository failures are server errors

RepositoryError maps to:

~~~text
500 Internal Server Error
~~~

The HTTP layer does not pretend a persistence failure is a client validation
error.

## 63. External integration failures map to 502

IntegrationError maps to:

~~~text
502 Bad Gateway
~~~

This distinguishes dependency failure from the API application's own domain
validation.

## 64. OpenAPI documents success and error contracts

Router decorators provide:

~~~text
response_model
responses
status_code
~~~

so FastAPI can generate typed OpenAPI contracts.

## 65. Reusable error-response groups keep documentation consistent

The integration exports:

~~~text
CREATE_ERROR_RESPONSES
LIST_ERROR_RESPONSES
READ_ERROR_RESPONSES
MUTATION_ERROR_RESPONSES
~~~

## 66. Create endpoints document 409, 422 and 500

CREATE_ERROR_RESPONSES contains:

~~~text
409
422
500
~~~

## 67. Read endpoints document 404, 422 and 500

READ_ERROR_RESPONSES contains:

~~~text
404
422
500
~~~

## 68. Mutation endpoints document 404, 409, 422 and 500

MUTATION_ERROR_RESPONSES contains:

~~~text
404
409
422
500
~~~

## 69. List endpoints document 422 and 500

LIST_ERROR_RESPONSES contains:

~~~text
422
500
~~~

## 70. OpenAPI errors reference ErrorResponse

Representative Contact GET documentation includes:

~~~text
200 -> ContactResponse
404 -> ErrorResponse
422 -> ErrorResponse
500 -> ErrorResponse
~~~

## 71. Error responses include examples

OpenAPI metadata includes examples such as:

~~~text
resource_not_found
domain_conflict
domain_validation
request_validation
repository_failure
integration_failure
~~~

## 72. OpenAPI qualification is selective

Tests do not snapshot the entire OpenAPI document.

They freeze important public contracts such as:

~~~text
path
method
request schema
success response schema
error status
ErrorResponse schema
examples
~~~

## 73. Selective OpenAPI tests reduce noise

Generated OpenAPI documents can contain framework-level ordering and metadata
details that are not meaningful compatibility guarantees.

Selective assertions focus on the intended public surface.

## 74. FastAPI request models preserve Decimal

Sales request schemas use Decimal-compatible fields.

Lead conversion and Opportunity creation therefore do not require conversion to
binary float at the HTTP boundary.

## 75. Response models preserve typed sales data

OpportunityResponse returns Decimal-backed values through Pydantic's JSON
serialization rules while preserving domain exactness internally.

## 76. The same router works with Memory

A test or local app can use:

~~~python
crm = CRM.memory()
~~~

and mount create_crm_router around it.

## 77. The same router works with SQLAlchemy/PostgreSQL

The reference application supplies a CRM whose Unit of Work factory returns
SQLAlchemyUnitOfWork instances.

No route code changes.

## 78. Reference PostgreSQL application owns infrastructure resources

The example application builds:

~~~text
SQLAlchemy Engine
Session factory
InProcessEventBus
base CRM facade
FastAPI application
~~~

inside its application composition layer.

## 79. One base CRM can produce per-request contextual views

CRMDependency receives a factory returning the base CRM.

Headers are then applied through CRM.with_context for the current request.

## 80. SQLAlchemy Sessions remain request-operation infrastructure

Routers never receive Session objects.

The CRM facade opens Unit of Work scopes internally through the runtime factory.

## 81. Reference application uses pool_pre_ping

The PostgreSQL engine is built with:

~~~text
pool_pre_ping = True
~~~

matching the production-reference infrastructure pattern from Chapter 24.

## 82. Application lifespan checks database connectivity

The example lifespan performs:

~~~text
SELECT 1
~~~

when entering application lifespan.

## 83. Application shutdown disposes the Engine

The ApplicationResources object calls:

~~~text
engine.dispose()
~~~

on shutdown.

Resource ownership remains explicit.

## 84. Schema migrations are not run at application startup

create_app explicitly does not invoke Alembic.

The deployment sequence is:

~~~text
install artifact
      |
      v
configure database URL
      |
      v
pycrmkit-migrate upgrade head
      |
      v
start ASGI application
~~~

## 85. Migration-first startup keeps schema changes observable

Application startup does not silently mutate production schema.

Migration execution can be managed independently by deployment tooling.

## 86. The example health endpoint checks PostgreSQL

The reference app exposes:

~~~text
GET /health
~~~

and executes SELECT 1 before returning:

~~~json
{
  "status": "ok",
  "database": "postgresql"
}
~~~

## 87. OpenAPI application version comes from the package

The reference app sets FastAPI's version from:

~~~text
pycrmkit.__version__
~~~

This avoids a duplicated version literal.

## 88. PostgreSQL API E2E starts from migrations

The E2E test:

~~~text
resets PostgreSQL schema
      |
      v
alembic upgrade head
      |
      v
create FastAPI app
~~~

It does not use Base.metadata.create_all as a production shortcut.

## 89. The E2E traverses multiple bounded contexts

The PostgreSQL HTTP journey creates:

~~~text
Contact
Organization
Relationship
Activity
Task
~~~

then completes the Task and reads Timeline state.

## 90. Request context is exercised in the PostgreSQL E2E

The Contact POST includes:

~~~text
X-Actor-ID
X-Correlation-ID
~~~

proving the same HTTP context bridge works on the durable persistence path.

## 91. Timeline E2E proves cross-feature composition

After Activity and Task operations, the Contact Timeline must include event
types such as:

~~~text
activity.created
task.created
task.completed
~~~

## 92. The E2E verifies typed 404 behavior

A missing Contact through PostgreSQL-backed HTTP still returns:

~~~text
404
contact.not_found
~~~

The persistence backend does not change the HTTP error contract.

## 93. Application restart is part of the test

The first FastAPI application instance is shut down.

A new application instance is created against the same PostgreSQL database.

## 94. Restart proves state is not process memory

The restarted app can reload the previously created Contact and Organization
data.

That demonstrates durable persistence through the full HTTP stack.

## 95. Installed-wheel FastAPI qualification is also required

The release gate builds the actual distribution and installs:

~~~text
wheel[fastapi,postgresql,migrations]
~~~

in a clean environment.

## 96. Installed-wheel smoke applies packaged migrations

The clean environment runs migration assets from the installed wheel before
starting the API smoke scenario.

This verifies Python code and packaged schema assets together.

## 97. Installed-wheel smoke also verifies OpenAPI

The release candidate qualification verifies OpenAPI through the installed
artifact, not only the repository source tree.

## 98. FastAPI integration is compatibility-governed

Within the stable 0.7.x integration line, documented behavior includes:

~~~text
route paths
HTTP methods
request schemas
success response schemas
ErrorResponse shape
status mapping
pagination semantics
request context propagation
OpenAPI generation
~~~

## 99. The HTTP layer does not expand domain capability arbitrarily

If the public CRM facade does not expose a read or mutation capability, the
FastAPI adapter should not bypass the facade to obtain it from an internal
repository.

This is why Leads and Opportunities remain command-oriented.

## 100. FastAPI is an adapter, not the application core

A useful mental model is:

~~~text
Transport
  |
  +--> HTTP
  +--> Pydantic
  +--> status codes
  +--> OpenAPI
  +--> headers

Application / Domain
  |
  +--> CRM facade
  +--> typed IDs
  +--> entities
  +--> value objects
  +--> business commands

Infrastructure
  |
  +--> Unit of Work
  +--> repositories
  +--> PostgreSQL
~~~

These layers interact through explicit boundaries.

## Common mistakes

### Returning ORM models from routes

FastAPI routes should return transport schemas built from domain entities.

### Injecting SQLAlchemy Session into CRM routers

The stable integration injects CRM, not Session.

### Calling repositories directly from endpoints

Routers should remain facade-first.

### Making domain entities inherit from Pydantic BaseModel

Transport models and domain models have different responsibilities.

### Treating Optional as sufficient PATCH semantics

Omission and explicit null must remain distinguishable.

### Returning raw FastAPI RequestValidationError payloads

The stable adapter normalizes them into ErrorResponse.

### Echoing submitted input in generic validation errors

PyCRMKit intentionally omits input echo from request-validation context.

### Mapping every failure to 400

The stable API distinguishes 404, 409, 422, 500 and 502 semantics.

### Inventing CRUD routes for command-oriented facades

HTTP integration should mirror the stable CRM facade rather than internal
repositories.

### Running Alembic automatically inside create_app

The reference deployment keeps migrations explicit.

### Using only Memory tests to qualify the HTTP layer

The stable integration also runs PostgreSQL-backed API E2E and restart
persistence tests.

### Assuming source-tree success proves packaging

The installed-wheel FastAPI/PostgreSQL smoke qualifies the distributable
artifact.

## Testing FastAPI integration

Transport-schema tests should cover:

~~~text
request validation
schema -> domain conversion
domain -> response conversion
typed UUID reconstruction
Decimal preservation
PATCH omitted/null/value semantics
JSON serialization
~~~

Dependency tests should cover:

~~~text
base context preservation
X-Actor-ID override
X-Correlation-ID override
both headers together
header bounds
~~~

Router tests should cover:

~~~text
route registration
success status codes
facade commands
list pagination
lifecycle transitions
Timeline composition
sales command flows
~~~

Error tests should cover:

~~~text
domain error -> HTTP status
ErrorResponse shape
request-validation normalization
no submitted-input echo
not-found through real route
conflict through real route
~~~

OpenAPI tests should cover:

~~~text
typed success schema
typed error schema
request body schema
documented status codes
documented examples
~~~

Production E2E should cover:

~~~text
PostgreSQL migrations
HTTP journey
request context
Timeline composition
typed errors
application shutdown
new application instance
durable reload
~~~

Packaging tests should cover:

~~~text
clean wheel install
FastAPI extra
PostgreSQL extra
migration assets
OpenAPI
API smoke
package version
~~~

## What you learned

You can now explain:

- why FastAPI remains optional;
- why the core does not import FastAPI;
- create_crm_router and CRMDependency;
- Pydantic transport versus domain entities;
- schema-to-domain and domain-to-schema mapping;
- typed IDs at the HTTP boundary;
- PATCH UNSET versus explicit null;
- command-oriented routers;
- pagination bridging;
- ErrorResponse and HTTP status mapping;
- request-validation normalization and privacy;
- OpenAPI compatibility qualification;
- Memory versus PostgreSQL wiring;
- migration-first startup;
- application resource ownership;
- PostgreSQL HTTP E2E and restart persistence;
- installed-wheel FastAPI qualification.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter              ✅
23 SQLAlchemy                  ✅
24 PostgreSQL                  ✅
25 Migrations                  ✅
26 FastAPI                     ✅
27 Django                      ← NEXT
28 Django REST Framework
29 Transactions & Unit of Work
30 Context, Events & Audit
31 Error Handling
32 Security & Privacy
~~~

The stack now reaches the HTTP boundary without changing domain ownership:

~~~text
HTTP
  |
  v
FastAPI
  |
  v
CRM facade
  |
  v
Domain
  |
  v
Persistence
~~~

## Next

The next chapter is **27 - Django**.

The next architecture will compare Django's application integration model with
the same PyCRMKit domain and persistence boundaries:

~~~text
Django Application
      |
      v
PyCRMKit Django bridge
      |
      v
CRM facade / repository contracts
      |
      v
Django ORM or configured persistence path
~~~

The next learning question is:

> How does PyCRMKit integrate with Django's application lifecycle, ORM,
> transactions, migrations and admin conventions without making the CRM domain
> depend on Django?
