# 01 — Core Concepts

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

Before adding more CRM features, this chapter builds the mental model behind
PyCRMKit. The goal is not to memorize implementation details; it is to understand
which layer owns which responsibility.

## What you will understand

By the end of this chapter you should be able to explain:

~~~text
Entity
Value Object
Typed ID
Entity Reference
Repository
Unit of Work
Domain Event
CRM Facade
Adapter
Context / Audit
~~~

and how they fit together.

## 1. Entity

An Entity has a stable domain identity.

PyCRMKit's base Entity defines equality by:

~~~text
concrete entity type
        +
typed domain ID
~~~

not by comparing every field.

Conceptually:

~~~python
contact_a.id == contact_b.id
~~~

is what makes two Contact instances represent the same domain entity.

Timestamped entities extend that convention with creation and update timestamps
normalized to UTC.

## 2. Typed IDs

PyCRMKit IDs are UUID-backed, but the domain does not treat every UUID as the
same thing.

Examples include:

~~~text
ContactId
OrganizationId
ActivityId
TaskId
RelationshipId
~~~

The common UUIDId primitive provides parsing and string conversion while each
bounded context exposes its own ID type.

This prevents accidental mixing such as passing an OrganizationId where a
ContactId is required.

The default runtime creates IDs with UUID4Factory.

## 3. Value Objects

A Value Object represents a value rather than an identity.

PyCRMKit's ValueObject convention is immutable. Examples include:

~~~text
ContactEmail
ContactPhone
Address
RelationshipEndpoint
RelationshipType
EntityReference
ActivityParticipant
Money
~~~

Value Objects are good places for normalization and validation.

For example, ContactEmail stores the original cleaned value and a normalized
comparison form. RelationshipType normalizes an open-ended relationship label
into a stable semantic code.

## 4. EntityReference

Some CRM concepts need to point at different entity types without loading those
entities.

EntityReference solves this with:

~~~text
kind + typed UUID-backed ID
~~~

Example:

~~~python
from pycrmkit.core.references import EntityReference

contact_ref = EntityReference(
    kind="contact",
    id=contact.id,
)
~~~

The kind is normalized to a stable lowercase identifier, and the ID must be a
PyCRMKit UUID-backed identifier.

EntityReference is used by cross-domain features such as Activities, Tasks,
Tags, Custom Fields and Timeline projections.

## 5. Repository

A Repository is a domain-owned persistence contract.

The important direction is:

~~~text
Domain
  ↓ defines
Repository Protocol
  ↑ implemented by
Infrastructure Adapter
~~~

Application/domain code should not need to know whether data is stored in
memory, SQLAlchemy/PostgreSQL or another future adapter.

Examples of public extension contracts include:

~~~text
ContactRepository
OrganizationRepository
RelationshipRepository
ActivityRepository
TaskRepository
TimelineRepository
LeadRepository
OpportunityRepository
...
~~~

This is why repository protocols belong to the bounded-context/domain side of
PyCRMKit instead of an ORM package.

## 6. Unit of Work

A Unit of Work groups repositories inside one transaction boundary.

The V1 UnitOfWork contract exposes the repositories used by the CRM domains and:

~~~text
commit()
rollback()
add_event(...)
context-manager lifecycle
~~~

The facade pattern is intentionally transactional. A typical mutation behaves
conceptually like:

~~~text
open Unit of Work
      ↓
load/use repository
      ↓
execute domain service
      ↓
record event/audit information
      ↓
commit
~~~

If the operation fails, the adapter can roll back the transaction.

CRM.memory() uses MemoryUnitOfWork. The production-reference persistence path
uses the SQLAlchemy Unit of Work with PostgreSQL.

## 7. CRM Facade

For application developers, the main public boundary is:

~~~python
from pycrmkit import CRM
~~~

CRM exposes transactional namespaces:

~~~text
crm.contacts
crm.organizations
crm.relationships
crm.activities
crm.tasks
crm.timeline
crm.leads
crm.opportunities
crm.pipelines
crm.tags
crm.custom_fields
crm.external_identities
crm.email
crm.events
crm.audit
crm.webhooks
~~~

The facade prevents application code from coordinating repositories and domain
services manually for common workflows.

For example:

~~~python
contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)
~~~

internally opens a Unit of Work, invokes ContactService, records the change and
commits.

## 8. Domain Events and event bus

PyCRMKit can publish DomainEvent objects after successful mutations.

CRM.memory() wires an InProcessEventBus by default.

The event foundation is separate from a transport technology. Events describe
domain facts; integrations decide what to do with them.

Examples of event types created by facade operations include:

~~~text
contact.created
organization.created
relationship.created
activity.created
task.created
task.started
task.completed
~~~

Event schemas and registry behavior are part of the frozen V1 contract.

## 9. Context and Audit

CRMContext carries cross-cutting operation metadata:

~~~text
actor_id
correlation_id
causation_id
~~~

You can create a contextual view of the same CRM:

~~~python
crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="onboarding-42",
)
~~~

The new facade view shares the same underlying storage/events while applying
that context to mutations.

This is useful for tracing a business flow across multiple operations.

## 10. Adapter

An Adapter implements an infrastructure boundary without changing the domain
contract.

Examples in PyCRMKit include:

~~~text
Memory storage adapter
SQLAlchemy persistence adapter
PostgreSQL production-reference path
FastAPI transport integration
Django ORM integration
Django REST Framework integration
SMTP / Resend email providers
~~~

A critical V1 architecture rule is:

~~~text
Transport / Framework
        ↓
CRM Facade
        ↓
Application / Domain
        ↓
Repository / Unit of Work contracts
        ↓
Infrastructure adapter
~~~

FastAPI and DRF qualification specifically guard against HTTP code bypassing the
CRM facade and reaching ORM implementation details directly.

## 11. Putting the concepts together

When you write:

~~~python
contact = crm.contacts.create(
    first_name="Ada",
    last_name="Lovelace",
)
~~~

the useful mental expansion is:

~~~text
Your code
   ↓
CRM
   ↓
Contacts facade
   ↓
ContactService
   ↓
ContactRepository
   ↓
Unit of Work
   ↓
Memory or SQLAlchemy adapter
   ↓
commit
   ↓
event + audit infrastructure
~~~

You normally work at the top of this stack. The lower layers become important
when you integrate PyCRMKit into production infrastructure or create your own
adapter.

## 12. What is public and what is internal?

The stable root package intentionally stays shallow:

~~~python
from pycrmkit import CRM, CRMConfig, CRMContext, __version__
~~~

Use public bounded-context exports and repository protocols when you need domain
types or extension contracts.

Avoid depending on internal implementation modules such as CRMRuntime, ORM model
classes or underscored helpers. Importability is not the same as a V1
compatibility guarantee.

## Common mistakes

### Treating an Entity like a DTO

Entities carry identity and domain semantics. They are not just transport
containers.

### Treating a Repository as a database helper

The Repository is a domain persistence abstraction. ORM models and SQL queries
belong behind the adapter.

### Calling ORM models directly from HTTP handlers

That bypasses the facade, transaction policy, events, audit and domain service
rules.

### Confusing Event and Audit

Events communicate domain facts. Audit answers traceability questions about
changes and operation context. They are related but not interchangeable.

## What you learned

You now have the architectural vocabulary needed for the rest of the course:

~~~text
Entity            identity
Value Object      immutable domain value
Typed ID          type-safe identity
EntityReference   cross-domain typed reference
Repository        persistence contract
Unit of Work      transaction boundary
Facade            application-facing API
Event             domain fact
Context / Audit   traceability
Adapter           infrastructure implementation
~~~

## Next

Continue with [02 — Your First CRM](02_first_crm.md). You will use these concepts
together in one small but complete customer workflow.
