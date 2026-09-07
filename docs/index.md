# PyCRMKit

PyCRMKit is a modular, headless Python CRM domain framework.

The current **`0.2.0b1`** milestone builds on the stable `0.1` CRM Core with first-class interaction history, transactional action items, and an event-projected customer Timeline:

```text
Application
    ↓
CRM facade
    ↓
Contacts / Organizations / Relationships / Activities / Tasks
    ↓
Domain services + policies + events
    ↓
Timeline projectors
    ↓
Unit of Work / Repository contracts
    ↓
Memory adapter
```

Start with:

```python
from pycrmkit import CRM
from pycrmkit.core.references import EntityReference

crm = CRM.memory()
contact = crm.contacts.create(first_name="Ada")
contact_ref = EntityReference("contact", contact.id)
task = crm.tasks.create(title="Prepare renewal", references=(contact_ref,))
crm.tasks.complete(task.id)

history = crm.timeline.for_contact(contact.id)
```

Activities record interactions that happened; Tasks represent follow-up work; Timeline is the read-oriented relationship history projected from meaningful domain events. Audit remains separate system mutation history.

Django, FastAPI, SQLAlchemy, PostgreSQL, communication providers, AI, and agent integrations remain optional later milestones.
