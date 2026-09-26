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

## 0.7.0a1 scope

The initial FastAPI foundation provides four integration modules:

```text
dependencies.py
schemas.py
errors.py
pagination.py
```

Routers are not part of `0.7.0a1`.

## Request-scoped CRM context

Create the CRM according to your application's storage/runtime strategy, then
pass a factory to `CRMDependency`:

```python
from typing import Annotated

from fastapi import Depends, FastAPI

from pycrmkit import CRM
from pycrmkit.integrations.fastapi import CRMDependency

crm = CRM.memory()
get_crm = CRMDependency(lambda: crm)

app = FastAPI()

@app.get("/context")
def context(current: Annotated[CRM, Depends(get_crm)]):
    return {
        "actor_id": current.context.actor_id,
        "correlation_id": current.context.correlation_id,
    }
```

The dependency recognizes:

```text
X-Actor-ID
X-Correlation-ID
```

and applies them with `CRM.with_context(...)`.

## Request schemas

Request schemas convert explicitly into the existing framework-neutral inputs.

```python
from pycrmkit.integrations.fastapi import ContactCreateRequest

payload = ContactCreateRequest(
    first_name="Ada",
    last_name="Lovelace",
)

contact = crm.contacts.create(**payload.to_domain_kwargs())
```

Update schemas keep omission distinct from explicit clearing:

```python
from pycrmkit.integrations.fastapi import ContactUpdateRequest

payload = ContactUpdateRequest(display_name=None)
changes = payload.to_domain()

crm.contacts.update(contact.id, changes)
```

The omitted fields become the domain's existing `UNSET` sentinel.

## Response schemas

Response schemas serialize domain entities explicitly:

```python
from pycrmkit.integrations.fastapi import ContactResponse

response = ContactResponse.from_domain(contact)
payload = response.model_dump(mode="json")
```

This avoids making Pydantic models part of the domain model.

## Pagination

Use `pagination_params` as a FastAPI dependency and convert it to
`OffsetPageRequest`:

```python
from typing import Annotated

from fastapi import Depends

from pycrmkit.integrations.fastapi import PaginationParams, pagination_params

def list_contacts(
    page: Annotated[PaginationParams, Depends(pagination_params)],
):
    domain_page = crm.contacts.search(page=page.to_domain())
    ...
```

Use `PageResponse.from_page(...)` to map a PyCRMKit `Page[T]` into a typed
API response.

## Error payload

`ErrorResponse` preserves the stable PyCRMKit error contract:

```python
from pycrmkit.integrations.fastapi import ErrorResponse

payload = ErrorResponse.from_error(error)
```

Status-code selection and exception-handler registration arrive in
`0.7.0b2 — OpenAPI/error mapping`.

## Dependency direction

FastAPI code may depend on PyCRMKit. PyCRMKit's domain must not depend on
FastAPI:

```text
router / dependency / schema
            ↓
         CRM facade
            ↓
          domain
```

The future router layer must continue to call the CRM facade/services rather
than SQLAlchemy ORM objects directly.
