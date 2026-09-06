# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The `0.0.x` line establishes the engineering foundation. Domain implementation begins with `0.1.0a1 — Core Primitives`.

## Architectural direction

```text
Application → PyCRMKit → Domain Services → Repository Contracts → Adapters
```

Django, FastAPI, SQLAlchemy, PostgreSQL, email providers, AI, and agent integrations remain optional capabilities.
