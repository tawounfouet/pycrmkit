# PyCRMKit Zero to Hero

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This learning path teaches PyCRMKit by building one CRM application progressively.
It complements the API/reference documentation: the guides focus on **how to build**,
while the domain/API pages remain the source of truth for individual contracts.

## Learning model

The path follows seven levels:

~~~text
LEVEL 0  Start
   ↓
LEVEL 1  CRM Core
   ↓
LEVEL 2  Customer Activity
   ↓
LEVEL 3  Sales
   ↓
LEVEL 4  Communication & Automation
   ↓
LEVEL 5  Data Operations
   ↓
LEVEL 6  Persistence & Integrations
   ↓
LEVEL 7  Production Applications
~~~

Every chapter extends the same mental model instead of introducing an unrelated
example application.

## Start here

1. [Getting Started](00_getting_started.md) — install PyCRMKit and create the first Contact.
2. [Core Concepts](01_core_concepts.md) — understand Entity, Value Object, typed ID, Repository, Unit of Work, Facade, Events and Adapters.
3. [Your First CRM](02_first_crm.md) — build a small in-memory CRM with Contact, Organization, Relationship, Activity, Task and Timeline.
4. [Contacts](03_contacts.md) — master the Contact aggregate, value objects, lifecycle, search and pagination.
5. [Organizations](04_organizations.md) — master company/account identity, domains, addresses, lifecycle and search.
6. [Relationships](05_relationships.md) — connect CRM entities with typed, directional and temporal relationships.
7. [Tags & Custom Fields](06_tags_and_custom_fields.md) — extend CRM entities with reusable classification and versioned typed business data.

## LEVEL 1 complete

Contacts, Organizations, Relationships, Tags and Custom Fields now form the complete CRM-core foundation. The next learning level is Customer Activity: Activities, Tasks and Timeline.

## Full Zero-to-Hero roadmap

The roadmap is intentionally broader than the pages currently published. Pages are
added in learning order and their examples are validated against the stable V1 API.

| Level | Chapter | Guide | Status |
| --- | ---: | --- | --- |
| 0 | 00 | Getting Started | Published |
| 0 | 01 | Core Concepts | Published |
| 0 | 02 | Your First CRM | Published |
| 1 | 03 | Contacts | Published |
| 1 | 04 | Organizations | Published |
| 1 | 05 | Relationships | Published |
| 1 | 06 | Tags & Custom Fields | Published |
| 2 | 07 | Activities | Planned |
| 2 | 08 | Tasks | Planned |
| 2 | 09 | Timeline | Planned |
| 3 | 10 | Leads | Planned |
| 3 | 11 | Opportunities | Planned |
| 3 | 12 | Pipelines | Planned |
| 3 | 13 | Lead Conversion | Planned |
| 4 | 14 | Email & Communications | Planned |
| 4 | 15 | Domain Events | Planned |
| 4 | 16 | Webhooks | Planned |
| 5 | 17 | External Identities | Planned |
| 5 | 18 | Importing Data | Planned |
| 5 | 19 | Deduplication | Planned |
| 5 | 20 | Contact Merge | Planned |
| 5 | 21 | Exporting Data | Planned |
| 6 | 22 | Memory Adapter | Planned |
| 6 | 23 | SQLAlchemy | Planned |
| 6 | 24 | PostgreSQL | Planned |
| 6 | 25 | Migrations | Planned |
| 6 | 26 | FastAPI | Planned |
| 6 | 27 | Django | Planned |
| 6 | 28 | Django REST Framework | Planned |
| 6 | 29 | Transactions & Unit of Work | Planned |
| 6 | 30 | Context, Events & Audit | Planned |
| 6 | 31 | Error Handling | Planned |
| 6 | 32 | Security & Privacy | Planned |
| 7 | 33 | Testing PyCRMKit Applications | Planned |
| 7 | 34 | Observability & Debugging | Planned |
| 7 | 35 | Performance | Planned |
| 7 | 36 | Application Architecture | Planned |
| 7 | 37 | Production Deployment | Planned |
| 7 | 38 | Complete FastAPI Application | Planned |
| 7 | 39 | Complete Django Application | Planned |
| 7 | 40 | Zero-to-Hero Final Project | Planned |

## How each guide is structured

Each chapter follows the same learning contract:

~~~text
What you will build
        ↓
Why the concept exists
        ↓
Mental model
        ↓
Minimal example
        ↓
Step-by-step implementation
        ↓
What happens internally
        ↓
Common mistakes
        ↓
Testing
        ↓
What you learned
        ↓
Next chapter
~~~

## Documentation boundaries

Use the documentation by intent:

| Need | Section |
| --- | --- |
| Learn by building | Zero-to-Hero Guides |
| Understand a domain concept | Domain/Core documentation |
| Check the frozen V1 contract | API / Compatibility |
| See infrastructure wiring | Integrations / Storage |
| Understand release guarantees | Releases / Security / Performance |

## Version policy

These guides target the stable V1 contract. Examples should remain executable on
PyCRMKit 1.0.x. When a future version changes a learning path, the guide should say
which version introduced the change instead of silently rewriting historical behavior.

Start with [00 — Getting Started](00_getting_started.md).
