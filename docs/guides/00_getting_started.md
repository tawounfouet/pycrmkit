# 00 — Getting Started

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter gets you from an empty Python environment to a working PyCRMKit
instance with your first CRM Contact.

## What you will build

By the end of this chapter you will have:

~~~text
Python
  ↓
PyCRMKit 1.0.0
  ↓
CRM.memory()
  ↓
Contact
~~~

The in-memory backend is deliberate. It lets you learn the domain API before
introducing SQLAlchemy, PostgreSQL, Django or FastAPI.

## Prerequisites

Use one of the V1-qualified Python versions:

~~~text
Python 3.11
Python 3.12
Python 3.13
~~~

## 1. Create an environment

~~~bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
~~~

On Windows PowerShell, activate the environment with:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

## 2. Install PyCRMKit

Install the framework-agnostic core:

~~~bash
pip install pycrmkit
~~~

Verify the installed version:

~~~bash
python -c "import pycrmkit; print(pycrmkit.__version__)"
~~~

For this guide the expected stable baseline is:

~~~text
1.0.0
~~~

The core installation does not require Django, FastAPI, SQLAlchemy or PostgreSQL.
Those integrations are optional and are introduced later in the learning path.

## 3. Create your first CRM instance

~~~python
from pycrmkit import CRM

crm = CRM.memory()
~~~

CRM.memory() creates a fully wired, isolated in-memory CRM with:

- a MemoryStore;
- a MemoryUnitOfWork factory;
- an in-process event bus;
- the default ID factory;
- the system clock;
- all public CRM facade namespaces.

No database or framework setup is required.

## 4. Create your first Contact

~~~python
from pycrmkit import CRM
from pycrmkit.contacts import ContactEmail

crm = CRM.memory()

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

print(contact.id)
print(contact.display_name)
~~~

The public entry point is the CRM facade:

~~~text
CRM
 └── contacts
      └── create(...)
~~~

You do not construct a repository or ContactService yourself for normal
application use. The facade opens a Unit of Work, executes the domain service,
records the mutation and commits the transaction.

## 5. Read the Contact back

~~~python
reloaded = crm.contacts.get(contact.id)

assert reloaded == contact
print(reloaded.display_name)
~~~

PyCRMKit entities use domain identity. A Contact is identified by ContactId,
which is a typed UUID-backed identifier rather than a raw string.

## 6. Add operation context

Real CRM mutations usually need to answer two questions:

~~~text
Who performed this operation?
Which business/request flow does it belong to?
~~~

Use a contextual facade view:

~~~python
crm = CRM.memory().with_context(
    actor_id="guide-user",
    correlation_id="zero-to-hero-001",
)

contact = crm.contacts.create(
    first_name="Grace",
    last_name="Hopper",
)
~~~

The contextual CRM shares the same storage and event system, but mutations carry
the configured actor/correlation metadata into event and audit infrastructure.

## Mental model

For the rest of the guides, keep this first model in mind:

~~~text
Your application
      ↓
CRM facade
      ↓
Domain service
      ↓
Repository contract
      ↓
Unit of Work
      ↓
Adapter
~~~

With CRM.memory(), the adapter is the in-memory implementation. Later we will
replace only the infrastructure side of this diagram.

## Common mistakes

### Importing internal facade classes

Prefer:

~~~python
from pycrmkit import CRM
~~~

Do not build applications around internal facade implementation classes such as
ContactsAPI or CRMRuntime. The stable V1 application entry point is CRM and its
public namespaces.

### Starting with PostgreSQL too early

PostgreSQL is the production-reference backend, but it introduces infrastructure
concerns that are unnecessary while learning Contact, Organization,
Relationship, Activity and Task semantics.

### Using raw strings as domain IDs

Let PyCRMKit create typed IDs and pass those typed IDs back to the public APIs.

## What you learned

You can now:

- install the stable framework;
- create an isolated CRM;
- create and retrieve a Contact;
- understand the purpose of CRM.memory();
- attach actor/correlation context;
- identify the facade as the normal application boundary.

## Next

Continue with [01 — Core Concepts](01_core_concepts.md) before adding more CRM
objects. That chapter explains the architecture behind the small amount of code
you just wrote.
