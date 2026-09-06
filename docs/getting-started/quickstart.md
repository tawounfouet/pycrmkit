# Quickstart

`0.1.0rc1` introduces the first high-level `CRM` facade. The in-memory backend is fully wired and requires no external service:

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

`0.1.0rc1` intentionally provides only the synchronous in-process bus. Durable outbox, retries, webhooks, and distributed delivery remain later roadmap items.

## Audit

Audit history is append-only and committed atomically with domain state:

```python
history = crm.audit.for_entity("contact", contact.id)
for entry in history.items:
    print(entry.action, entry.occurred_at)
```

The facade records changed field names rather than copying raw contact/customer values into audit metadata by default.
