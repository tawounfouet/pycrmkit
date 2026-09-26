# Django REST Framework Integration

PyCRMKit's DRF integration is optional and transport-only. It does not make the
domain depend on Django REST Framework and it does not turn Django ORM models
into API/domain entities.

## Install

```bash
pip install "pycrmkit[drf]"
```

The plain Django adapter remains independent:

```bash
pip install "pycrmkit[django]"
```

That installation does not install `rest_framework`.

## Architecture

```text
DRF request
    ↓
PyCRMKit serializer / ViewSet
    ↓
CRM facade
    ↓
domain service
    ↓
Unit of Work / Repository Protocol
    ↓
Memory / SQLAlchemy / Django / custom adapter
```

The DRF layer never reaches directly into Django ORM models or repository
internals.

## CRM factory

The consuming application owns persistence and CRM construction.

Configure a callable or dotted import path:

```python
PYCRMKIT_CRM_FACTORY = "project.crm.get_crm"
```

For example:

```python
from pycrmkit import CRM

crm = CRM.memory()

def get_crm() -> CRM:
    return crm
```

Production wiring can return a CRM backed by an application-selected Unit of
Work instead.

## Router

```python
from django.urls import include, path
from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()

urlpatterns = [
    path("crm/", include(router.urls)),
]
```

The beta router exposes:

```text
GET    /crm/contacts/
POST   /crm/contacts/
GET    /crm/contacts/{id}/
PATCH  /crm/contacts/{id}/
POST   /crm/contacts/{id}/archive/

GET    /crm/organizations/
POST   /crm/organizations/
GET    /crm/organizations/{id}/
PATCH  /crm/organizations/{id}/
POST   /crm/organizations/{id}/archive/

GET    /crm/relationships/
POST   /crm/relationships/
GET    /crm/relationships/{id}/
PATCH  /crm/relationships/{id}/
POST   /crm/relationships/{id}/end/
```

Full replacement with `PUT` is intentionally not part of this helper surface;
PyCRMKit's domain APIs use explicit partial-update DTO semantics.

## Serializers

The bridge includes serializer helpers for the same aggregate families,
including nested Contact email/phone/address values, Organization
domain/address values, and typed Relationship endpoints.

Serializer validation handles HTTP shape/types. Conversion then constructs the
existing PyCRMKit domain value objects and update DTOs so domain validation
remains authoritative.

Partial updates preserve the distinction between:

```text
field omitted       → UNSET / no mutation
field = null        → explicit clear, where the domain allows it
invalid null        → request validation error
```

## Pagination

List routes expose the framework-neutral offset contract:

```json
{
  "items": [],
  "limit": 50,
  "offset": 0,
  "total": 0,
  "has_next": false,
  "has_previous": false
}
```

Bounds come from `OffsetPageRequest`, including its maximum limit.

## Request context

The ViewSets recognize:

```text
X-Actor-ID
X-Correlation-ID
```

and pass those values through `CRM.with_context(...)`. The transport does not
invent authentication or authorization behavior.

## Error mapping

PyCRMKit domain errors retain stable machine-readable codes:

```text
ValidationError      → 422
NotFoundError        → 404
ConflictError        → 409
RepositoryError      → 500
IntegrationError     → 502
other PyCRMKitError  → 500
```

The response shape is:

```json
{
  "code": "contact.not_found",
  "message": "Contact not found",
  "context": {}
}
```

DRF serializer/request validation is normalized separately:

```json
{
  "code": "request.validation_error",
  "message": "request validation failed",
  "context": {
    "errors": [
      {
        "code": "invalid",
        "location": ["status", "0"],
        "message": "..."
      }
    ]
  }
}
```

Submitted input values are not copied into that normalized error context.

Packaged PyCRMKit ViewSets invoke this bridge directly. To apply it to
application-owned DRF views too:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "pycrmkit.integrations.django.drf.errors."
        "pycrmkit_exception_handler"
    ),
}
```

## Current boundary

`0.8.0b2` is not yet the Django release candidate. It deliberately does not
claim:

```text
reference Django application
Django + PostgreSQL application E2E
full cross-domain DRF surface
stable 0.8.x compatibility
```

Those are qualified in the subsequent release-candidate/stable milestones.

## Next

**`0.8.0rc1 — Django Example + E2E`**.
