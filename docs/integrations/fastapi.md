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

## 0.7.0b2 scope

The FastAPI integration now provides:

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

Milestone progression:

```text
0.7.0a1  schemas + dependency bridge
0.7.0b1  reusable routers
0.7.0b2  OpenAPI + error mapping
```

The reference PostgreSQL application remains the `0.7.0rc1` milestone.

## Application setup

The consuming application owns the CRM factory and storage/runtime wiring.

```python
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
```

The same router and handler layer can be mounted around a
SQLAlchemy/PostgreSQL-backed CRM without changing route code.

## Dependency direction

The architectural invariant remains:

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

The integration never routes directly to SQLAlchemy models or Sessions.

## Request context

`CRMDependency` recognizes:

```text
X-Actor-ID
X-Correlation-ID
```

and applies them through `CRM.with_context(...)`.

## Error contract

All mapped PyCRMKit errors use:

```json
{
  "code": "resource.not_found",
  "message": "resource not found",
  "context": {}
}
```

The public model is `ErrorResponse`.

### Domain error → HTTP status

```text
ValidationError              → 422 Unprocessable Content
NotFoundError                → 404 Not Found
ConflictError                → 409 Conflict
DuplicateError               → 409 Conflict
InvalidStateError            → 409 Conflict
RepositoryError              → 500 Internal Server Error
IntegrationError             → 502 Bad Gateway
PyCRMKitError fallback       → 500 Internal Server Error
```

Use `status_code_for_error(...)` when an application needs the mapping
independently from the handler.

## Request validation

FastAPI/Pydantic request-validation failures are normalized to the same
`ErrorResponse` shape:

```json
{
  "code": "request.validation_error",
  "message": "request validation failed",
  "context": {
    "errors": [
      {
        "type": "missing",
        "location": ["body", "field"],
        "message": "Field required"
      }
    ]
  }
}
```

Validation context intentionally omits the submitted input value. This avoids
echoing request-body data into a generic API error payload.

## Exception handlers

Install the integration handlers explicitly:

```python
from pycrmkit.integrations.fastapi import install_error_handlers

install_error_handlers(app)
```

This registers handlers for:

```text
PyCRMKitError
RequestValidationError
```

The helper returns the application, so chaining is also possible.

## OpenAPI contract

Router decorators now document typed error responses in addition to typed
success responses.

Reusable groups are available:

```python
CREATE_ERROR_RESPONSES
LIST_ERROR_RESPONSES
READ_ERROR_RESPONSES
MUTATION_ERROR_RESPONSES
```

Each documented error response references `ErrorResponse` and includes
status-specific examples.

Representative endpoint:

```text
GET /crm/contacts/{contact_id}

200 ContactResponse
404 ErrorResponse
422 ErrorResponse
500 ErrorResponse
```

Mutation example:

```text
POST /crm/tasks/{task_id}/complete

200 TaskResponse
404 ErrorResponse
409 ErrorResponse
422 ErrorResponse
500 ErrorResponse
```

OpenAPI qualification is selective rather than a snapshot of the entire
document. This keeps compatibility checks focused on public method/path/status,
request schema, response schema and example contracts.

## Router surface

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

State-changing domain operations remain explicit commands:

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

Leads and Opportunities still mirror their public CRM facade surface rather
than reaching through internal repositories.

## Pagination

List and Timeline routes continue to reuse:

```text
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

Bounds:

```text
limit: 1..200
offset: >= 0
default limit: 50
```

## Qualification

`0.7.0b2` adds tests for:

- error status mapping;
- stable `ErrorResponse` shape;
- request-validation normalization;
- domain ValidationError through a real router;
- NotFoundError through a real router;
- InvalidStateError / conflict through a real router;
- no submitted-input echo in validation context;
- typed OpenAPI success responses;
- typed OpenAPI error responses;
- OpenAPI examples;
- Lead conversion request/response OpenAPI contracts;
- all existing router flows with installed handlers;
- continued core import independence from FastAPI.

## Next milestone

`0.7.0rc1 — FastAPI Example + E2E` will add:

```text
examples/fastapi_postgres/
PostgreSQL-backed API E2E
reference application wiring
full FastAPI release-candidate qualification
```
