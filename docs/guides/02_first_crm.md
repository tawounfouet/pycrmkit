# 02 — Your First CRM

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter turns the first Contact from the previous guide into a small CRM
workflow. We will connect a person to an organization, log an interaction,
create and complete a task, then inspect the customer's Timeline.

## What you will build

~~~text
Contact
   │
   ├────────────── Relationship ────────────── Organization
   │                                               │
   ├── Activity                                    │
   │                                               │
   └── Task                                        │
          │                                        │
          └────────────── Timeline ─────────────────┘
~~~

Everything still runs in memory so the domain model remains the focus.

## 1. Create a contextual CRM

~~~python
from pycrmkit import CRM

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="first-crm-001",
)
~~~

The context is optional, but using it from the beginning makes later event and
audit examples easier to understand.

## 2. Create a Contact

~~~python
from pycrmkit.contacts import ContactEmail

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
    emails=(
        ContactEmail(
            "ada@example.com",
            is_primary=True,
        ),
    ),
)
~~~

The Contact owns a typed ContactId:

~~~python
print(contact.id)
print(contact.display_name)
~~~

## 3. Create an Organization

~~~python
organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
    source="zero-to-hero",
)
~~~

Organizations and Contacts are separate aggregates. A CRM relationship between
them is represented explicitly instead of embedding one inside the other.

## 4. Connect the Contact and Organization

~~~python
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipType,
)

relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    role="founder",
    is_primary=True,
)
~~~

RelationshipEndpoint preserves the type of each side:

~~~text
contact endpoint       → ContactId
organization endpoint  → OrganizationId
~~~

RelationshipType is open-ended. The value is normalized into a stable semantic
code rather than forced into a closed enum.

## 5. Create generic entity references

Activities and Tasks can reference different CRM entity types. For that, use
EntityReference:

~~~python
from pycrmkit.core.references import EntityReference

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)

organization_ref = EntityReference(
    kind="organization",
    id=organization.id,
)
~~~

These references point to entities without loading the aggregate itself.

## 6. Log an Activity

~~~python
from pycrmkit.activities import ActivityParticipant

activity = crm.activities.log(
    type="meeting",
    subject="CRM discovery session",
    description="Discussed the initial customer relationship.",
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
    references=(organization_ref,),
    source="zero-to-hero",
)
~~~

This records a CRM interaction rather than a future action.

A useful distinction is:

~~~text
Activity
= something that happened

Task
= something that should happen
~~~

## 7. Create a Task

~~~python
task = crm.tasks.create(
    title="Prepare the first proposal",
    priority="high",
    references=(
        contact_ref,
        organization_ref,
    ),
    source="zero-to-hero",
)
~~~

The task can now move through its lifecycle:

~~~python
task = crm.tasks.start(task.id)
task = crm.tasks.complete(task.id)
~~~

The public task facade owns those transitions. Application code should not
mutate the status field directly.

## 8. Read the Contact Timeline

~~~python
timeline = crm.timeline.for_contact(contact.id)

for entry in timeline.items:
    print(
        entry.occurred_at,
        entry.event_type,
    )
~~~

The Timeline is a read-only customer relationship history. Because the Activity
and Task reference the Contact, their relevant events can appear in the
Contact's timeline projection.

You can also inspect an Organization timeline:

~~~python
organization_timeline = crm.timeline.for_organization(
    organization.id,
)
~~~

## 9. Reload the objects

The public facade gives you typed reads:

~~~python
assert crm.contacts.get(contact.id) == contact
assert crm.organizations.get(organization.id) == organization
assert crm.relationships.get(relationship.id) == relationship
assert crm.activities.get(activity.id) == activity

completed_task = crm.tasks.get(task.id)
print(completed_task.status)
~~~

Even with the Memory adapter, work still goes through the same public facade and
transactional contracts used by the architecture.

## 10. The complete example

~~~python
from pycrmkit import CRM
from pycrmkit.activities import ActivityParticipant
from pycrmkit.contacts import ContactEmail
from pycrmkit.core.references import EntityReference
from pycrmkit.relationships import (
    RelationshipEndpoint,
    RelationshipType,
)

crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="first-crm-001",
)

contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
    emails=(
        ContactEmail(
            "ada@example.com",
            is_primary=True,
        ),
    ),
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
    source="zero-to-hero",
)

relationship = crm.relationships.create(
    source=RelationshipEndpoint.contact(contact.id),
    target=RelationshipEndpoint.organization(organization.id),
    relationship_type=RelationshipType("employment"),
    role="founder",
    is_primary=True,
)

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)
organization_ref = EntityReference(
    kind="organization",
    id=organization.id,
)

activity = crm.activities.log(
    type="meeting",
    subject="CRM discovery session",
    participants=(
        ActivityParticipant(
            reference=contact_ref,
            role="customer",
            is_primary=True,
        ),
    ),
    references=(organization_ref,),
)

task = crm.tasks.create(
    title="Prepare the first proposal",
    priority="high",
    references=(contact_ref, organization_ref),
)

crm.tasks.start(task.id)
completed_task = crm.tasks.complete(task.id)

timeline = crm.timeline.for_contact(contact.id)

print(contact.display_name)
print(organization.display_name)
print(relationship.relationship_type)
print(activity.subject)
print(completed_task.status)

for entry in timeline.items:
    print(entry.occurred_at, entry.event_type)
~~~

## What happens internally?

Each mutation follows the same broad path:

~~~text
guide code
   ↓
CRM namespace
   ↓
domain service
   ↓
repository contract
   ↓
Unit of Work
   ↓
Memory adapter
   ↓
commit
   ↓
event / timeline / audit infrastructure
~~~

This is why the same domain workflow can later move to PostgreSQL without
rewriting your business vocabulary.

## Common mistakes

### Storing organization fields directly on Contact

Use a Relationship when you need to model a semantic link between two CRM
entities.

### Using RelationshipEndpoint everywhere

RelationshipEndpoint is specialized for Relationship participants.
EntityReference is the generic cross-domain reference used by features such as
Activities and Tasks.

### Treating Activity and Task as the same concept

Activity records interaction history. Task models actionable work and has an
explicit lifecycle.

### Building UI or ORM code before understanding the domain

The guide intentionally starts headless. FastAPI, Django and persistence become
much easier once the Contact → Organization → Activity → Task model is clear.

## What you learned

You can now build a small CRM that:

- stores a Contact;
- stores an Organization;
- connects them with a typed Relationship;
- logs an Activity;
- creates and completes a Task;
- uses EntityReference for cross-domain links;
- reads customer history from Timeline;
- keeps operation context attached to the workflow.

## Where we go next

The foundation is now in place. The next learning block expands each CRM concept
individually:

~~~text
03 Contacts
04 Organizations
05 Relationships
06 Tags & Custom Fields
~~~

Return to the [Zero-to-Hero roadmap](index.md) for the complete path.
