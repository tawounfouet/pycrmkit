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

The `0.8.0a1` alpha targets Django 5.2 LTS while preserving PyCRMKit's Python
3.11–3.13 compatibility matrix.

Add the PyCRMKit application explicitly:

```python
INSTALLED_APPS = [
    # ...
    "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
]
```

At `0.8.0a1`, the adapter provides the app bootstrap plus initial ORM models
and repositories. Django migrations, the transaction bridge and admin helpers
are scheduled for `0.8.0b1`; do not treat the alpha as a migration-complete
Django deployment yet.

## Repository development

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```
