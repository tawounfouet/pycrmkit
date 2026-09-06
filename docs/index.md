# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current `0.1.0a2` milestone implements the first complete vertical slice: **Contacts**.

```text
Application → ContactService → ContactRepository → Adapter
```

The core remains framework-agnostic. Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations remain optional capabilities.
