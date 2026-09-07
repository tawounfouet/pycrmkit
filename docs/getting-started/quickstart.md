# Quickstart

`0.1.0` provides the stable high-level `CRM` facade. The in-memory backend is fully wired and requires no external service:

```python
from pycrmkit import CRM
from pycrmkit.contacts import ContactEmail
from pycrmkit.core.references import EntityReference
from pycrmkit.custom_fields import CustomFieldType
from pycrmkit.relationships import RelationshipEndpoint, RelationshipType

crm = CRM.memory()

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
    emails=(ContactEmail("ada@example.com", is_primary=True),),
)
organization = crm.organizations.create(legal_name="Analytical Engines Ltd")
crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
)

contact_ref = EntityReference("contact", contact.id)
vip = crm.tags.create("VIP")
crm.tags.assign(vip.id, contact_ref)

tier = crm.custom_fields.define(
    key="customer_tier",
    label="Customer Tier",
    field_type=CustomFieldType.STRING,
    applies_to=("contact",),
)
crm.custom_fields.set_value(tier.id, contact_ref, "gold")
```

## Actor and correlation context

Use a scoped facade view to attach actor/correlation metadata to every mutation without changing storage or subscriptions:

```python
scoped = crm.with_context(actor_id="user-42", correlation_id="request-123")
scoped.contacts.create(first_name="Grace")
```

## Events and Audit

Facade mutations stage events in the current Unit of Work and dispatch them only after a successful commit. Audit history is append-only and committed atomically with domain state.

```python
@crm.events.on("contact.created")
def on_contact_created(event):
    print(event.aggregate_id)

history = crm.audit.for_entity("contact", contact.id)
```

Audit records system mutation history. It is intentionally distinct from the customer-facing Timeline.

## Activities

`0.2.0a1` adds generic interaction history without provider dependencies:

```python
from pycrmkit.activities import ActivityParticipant, ActivityQuery

call = crm.activities.log(
    type="call",
    subject="Commercial follow-up",
    direction="outbound",
    duration_seconds=480,
    participants=(ActivityParticipant(contact_ref, role="customer", is_primary=True),),
)

history = crm.activities.list(ActivityQuery(participant=contact_ref))
```

## Tasks

`0.2.0a2` adds transactional CRM action items with explicit lifecycle transitions:

```python
from pycrmkit.tasks import TaskQuery

follow_up = crm.tasks.create(
    title="Prepare renewal proposal",
    priority="high",
    assignee_id="seller-7",
    references=(contact_ref,),
)
follow_up = crm.tasks.start(follow_up.id)
follow_up = crm.tasks.complete(follow_up.id)
completed = crm.tasks.list(TaskQuery(status="completed"))
```

## Timeline

`0.2.0b1` projects meaningful Activity and Task lifecycle events into immutable relationship history:

```python
contact_history = crm.timeline.for_contact(contact.id)
organization_history = crm.timeline.for_organization(organization.id)

for entry in contact_history.items:
    print(entry.occurred_at, entry.event_type, entry.title)
```

`activity.created` uses the Activity business `occurred_at` timestamp. Task creation and lifecycle transitions use their domain lifecycle timestamps. Ordering is deterministic and reverse chronological. Generic `activity.updated` / `task.updated` mutations are deliberately not projected to keep customer history meaningful rather than audit-like.
