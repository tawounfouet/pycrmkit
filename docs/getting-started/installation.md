# Installation

PyCRMKit `0.6.0` is the current stable Persistence Foundation release.
The latest integration prerelease is `0.7.0rc1 — FastAPI Example + E2E`.

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

For the PostgreSQL-backed FastAPI reference path, install the compatible extras
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

## Repository development

```bash
git clone https://github.com/tawounfouet/pycrmkit.git
cd pycrmkit
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
```
