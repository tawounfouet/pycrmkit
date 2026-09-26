# Installation

PyCRMKit `0.7.0` is the current stable FastAPI Integration release.

## Core

The core package remains framework-agnostic:

```bash
pip install pycrmkit
```

Verify:

```bash
python -c "import pycrmkit; print(pycrmkit.__version__)"
```

## FastAPI integration

Install the optional FastAPI bridge with:

```bash
pip install "pycrmkit[fastapi]"
```

This adds FastAPI/Pydantic transport support, request-scoped dependency bridging,
reusable routers, error handlers and OpenAPI error contracts without making them
core runtime dependencies.

For the stable PostgreSQL-backed FastAPI reference path, install the compatible extras
together:

```bash
pip install "pycrmkit[fastapi,postgresql,migrations]"
```

The reference application is available in `examples/fastapi_postgres/`.

## SQLAlchemy / PostgreSQL

For SQLAlchemy persistence:

```bash
pip install "pycrmkit[sqlalchemy]"
```

For the PostgreSQL production-reference backend:

```bash
pip install "pycrmkit[postgresql]"
```

For packaged Alembic migration tooling:

```bash
pip install "pycrmkit[migrations]"
```

## Django integration

Install the optional Django bridge with:

```bash
pip install "pycrmkit[django]"
```

The stable `0.8.0` Django integration targets Django 5.2 LTS while preserving PyCRMKit's
Python 3.11–3.13 compatibility matrix.

Add the PyCRMKit application explicitly:

```python
INSTALLED_APPS = [
    # ...
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
```

At `0.8.0b1`, the adapter provides its initial ORM models/repositories, packaged
Django migration `0001_initial`, admin helpers, and an explicit transaction bridge.
Apply the adapter migration through Django's normal deployment lifecycle:

```bash
python manage.py migrate pycrmkit_crm
```

Transactional code may use:

```python
from pycrmkit.integrations.django.transactions import DjangoTransactionBridge

with DjangoTransactionBridge() as bridge:
    bridge.contacts.save(contact)
    bridge.commit()
```

The bridge currently exposes the Django repositories implemented by the `0.8.x`
line (Contacts, Organizations and Relationships); it is not yet the complete
cross-domain `UnitOfWork` implementation.

## Django REST Framework integration

DRF is a separate optional capability. Installing the plain Django adapter does
not install Django REST Framework:

```bash
pip install "pycrmkit[drf]"
```

Configure an application-owned CRM factory:

```python
PYCRMKIT_CRM_FACTORY = "project.crm.get_crm"
```

or provide any callable through the same setting. Mount the reusable router:

```python
from django.urls import include, path
from pycrmkit.integrations.django.drf import create_drf_router

router = create_drf_router()

urlpatterns = [
    path("crm/", include(router.urls)),
]
```

For consistent error handling across additional application-owned DRF views:

```python
REST_FRAMEWORK = {
    "EXCEPTION_HANDLER": (
        "pycrmkit.integrations.django.drf.errors."
        "pycrmkit_exception_handler"
    ),
}
```

The packaged PyCRMKit ViewSets already normalize PyCRMKit domain errors and DRF
request-validation errors. The global setting extends the same handler to other
DRF views in the consuming application.

## Django + PostgreSQL reference application

The release-candidate example is available under `examples/django/`.

Install the required capabilities together:

```bash
pip install "pycrmkit[django,drf,postgresql]"
```

Then configure `PYCRMKIT_DATABASE_URL`, apply Django migrations explicitly and
start the project:

```bash
python examples/django/manage.py migrate
python examples/django/manage.py runserver
```

The reference path uses PostgreSQL 17 and never runs migrations implicitly at
import or startup time.

## Repository development

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```
