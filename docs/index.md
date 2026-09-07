# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.2.0a1`** milestone builds on the stable `0.1` CRM Core and introduces first-class interaction history:

```text
Application
    ↓
CRM facade
    ↓
Contacts / Organizations / Relationships / Activities
    ↓
Domain services + policies
    ↓
Unit of Work
    ↓
Repository contracts
    ↓
Memory adapter
```

Start with:

```python
from pycrmkit import CRM

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada")
activity = crm.activities.log(
    type="call",
    subject="Commercial follow-up",
    direction="outbound",
)
```

Activities are generic CRM records. They do not send email, place calls, store documents, or orchestrate workflows.

Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations remain optional later milestones.
