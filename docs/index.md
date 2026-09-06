# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.1.0rc1`** milestone completes the first integrated CRM Core candidate:

```text
Application
    ↓
CRM facade
    ↓
Domain services + policies
    ↓
Unit of Work
    ↓
Repository contracts
    ↓
Memory adapter
```

The candidate includes Contacts, Organizations, Relationships, Tags, versioned Custom Fields, domain events, append-only audit history, and a transactional in-memory backend.

Start with:

```python
from pycrmkit import CRM

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada")
```

Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations remain optional later milestones.
