# Quickstart

`0.1.0` provides the first stable high-level `CRM` facade. The in-memory backend is fully wired and requires no external service:

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
scoped = crm.with_context(
    actor_id="user-42",
    correlation_id="request-123",
)

scoped.contacts.create(first_name="Grace")
```

The new view shares the same backend as `crm`.

## Events

Facade mutations stage events in the current Unit of Work and dispatch them only after a successful commit:

```python
@crm.events.on("contact.created")
def on_contact_created(event):
    print(event.aggregate_id)
```

`0.1.0` intentionally provides only the synchronous in-process bus. Durable outbox, retries, webhooks, and distributed delivery remain later roadmap items.

## Audit

Audit history is append-only and committed atomically with domain state:

```python
history = crm.audit.for_entity("contact", contact.id)
for entry in history.items:
    print(entry.action, entry.occurred_at)
```

The facade records changed field names rather than copying raw contact/customer values into audit metadata by default.


## Activities

`0.2.0a1` adds generic interaction history without introducing provider dependencies:

```python
from pycrmkit.activities import ActivityParticipant, ActivityQuery
from pycrmkit.core.references import EntityReference

contact_ref = EntityReference("contact", contact.id)

call = crm.activities.log(
    type="call",
    subject="Commercial follow-up",
    direction="outbound",
    duration_seconds=480,
    participants=(
        ActivityParticipant(contact_ref, role="customer", is_primary=True),
    ),
)

history = crm.activities.list(
    ActivityQuery(participant=contact_ref)
)
```

Activity events are committed and dispatched using the same Unit-of-Work, EventBus, and Audit foundation as the CRM Core.


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

Task state transitions, audit writes, and domain events participate in the same Unit-of-Work semantics as the CRM Core and Activities.
