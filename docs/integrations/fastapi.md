# FastAPI Integration

PyCRMKit's FastAPI support is optional and additive.

Install it with:

```bash
pip install "pycrmkit[fastapi]"
```

The core package remains framework-agnostic:

```python
import pycrmkit
```

does not import FastAPI.

## 0.7.0b1 scope

The FastAPI integration now contains:

```text
dependencies.py
schemas.py
errors.py
pagination.py
router.py
routers/
├── contacts.py
├── organizations.py
├── relationships.py
├── activities.py
├── tasks.py
├── leads.py
├── opportunities.py
└── timeline.py
```

`0.7.0a1` supplied transport schemas and the dependency bridge.
`0.7.0b1` adds the reusable HTTP routing layer.

## Mount the complete CRM router

The consuming application owns the CRM factory and chooses its storage/runtime
configuration:

```python
from fastapi import FastAPI

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import create_crm_router

crm = CRM.memory()

app = FastAPI()
app.include_router(
    create_crm_router(lambda: crm),
    prefix="/crm",
)
```

The same router factory can be used with a SQLAlchemy/PostgreSQL-wired CRM
without changing router code.

## Request-scoped CRM context

Every route is backed by `CRMDependency`. The dependency recognizes:

```text
X-Actor-ID
X-Correlation-ID
```

and applies them through `CRM.with_context(...)`.

The HTTP layer therefore preserves the existing actor/correlation semantics
rather than introducing a second context model.

## Router surface

The beta exposes facade-backed routes for:

```text
/contacts
/organizations
/relationships
/activities
/tasks
/leads
/opportunities
/timeline
```

Contacts, Organizations, Relationships, Activities and Tasks expose the
read/write operations already available from their public CRM facade
namespaces.

State-changing domain operations remain explicit commands, for example:

```text
POST /contacts/{id}/archive
POST /relationships/{id}/end
POST /tasks/{id}/start
POST /tasks/{id}/complete
POST /tasks/{id}/cancel
POST /tasks/{id}/reopen
POST /leads/{id}/qualify
POST /leads/{id}/disqualify
POST /leads/{id}/convert
POST /opportunities/{id}/move
```

Timeline remains read-only.

## Public-facade boundary

The architectural invariant is:

```text
HTTP Request
     ↓
FastAPI Router
     ↓
Pydantic transport schema
     ↓
CRMDependency
     ↓
CRM Facade
     ↓
Domain / Application Services
     ↓
Repository Contracts
     ↓
Adapter
```

Not:

```text
FastAPI Router
     ↓
SQLAlchemy Model / Session
```

`0.7.0b1` deliberately does not create Lead or Opportunity read endpoints by
accessing `CRM._runtime` or repositories. Those namespaces currently expose
command-oriented public facade APIs, and the router respects that boundary.

## Request and response schemas

Request schemas convert explicitly into framework-neutral domain inputs:

```python
from pycrmkit.integrations.fastapi import ContactCreateRequest

payload = ContactCreateRequest(
    first_name="Ada",
    last_name="Lovelace",
)

contact = crm.contacts.create(**payload.to_domain_kwargs())
```

Update schemas keep omission distinct from explicit clearing:

```text
field omitted    → domain UNSET
field = null     → explicit clear, where allowed
field = value    → explicit replacement
```

Pydantic models remain transport models, never domain Entities.

## Pagination

List and Timeline routes reuse the stable domain pagination contract:

```text
HTTP limit/offset
       ↓
PaginationParams
       ↓
OffsetPageRequest
       ↓
CRM facade
       ↓
Page[T]
       ↓
PageResponse[T]
```

Bounds remain:

```text
limit: 1..200
offset: >= 0
default limit: 50
```

## Error payload foundation

`ErrorResponse` still preserves the stable PyCRMKit error contract:

```python
from pycrmkit.integrations.fastapi import ErrorResponse

payload = ErrorResponse.from_error(error)
```

Global domain-error → HTTP status selection, exception-handler registration and
the final OpenAPI error contract are intentionally deferred to
`0.7.0b2 — OpenAPI / Error Mapping`.

## Qualification

The router integration suite exercises:

- composite router registration;
- Contact and Organization HTTP lifecycle operations;
- Relationship, Activity, Task and Timeline composition;
- offset pagination through the HTTP layer;
- Lead qualification/conversion and Opportunity movement;
- request-scoped actor/correlation propagation through the existing dependency
  bridge;
- continued core import independence from FastAPI.

The PostgreSQL-backed example API and full cross-capability API E2E remain the
`0.7.0rc1` milestone.
