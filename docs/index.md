# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.2.0a2`** milestone builds on the stable `0.1` CRM Core with first-class interaction history and transactional action items:

```text
Application
    ↓
CRM facade
    ↓
Contacts / Organizations / Relationships / Activities / Tasks
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
task = crm.tasks.create(title="Prepare renewal", priority="high")
```

Activities record interactions that happened; Tasks represent work still to perform. Neither domain sends email, places calls, stores documents, or orchestrates workflows.

Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations remain optional later milestones.
