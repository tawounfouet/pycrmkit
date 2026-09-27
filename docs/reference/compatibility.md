# Compatibility

This page records the currently qualified compatibility baseline for PyCRMKit.

## Current stable line

```text
PyCRMKit 0.9.0 — Data Operations Stable
```

The previously stabilized Django integration remains compatibility-governed
within the `0.8.x` line; `0.9.0` becomes the current project-wide stable
milestone.

## Python

The current CI matrix qualifies:

```text
Python 3.11
Python 3.12
Python 3.13
```

## Core installation

The core package remains framework-agnostic and has no mandatory runtime
dependency on FastAPI, Pydantic, SQLAlchemy, Django or Django REST Framework.

```bash
pip install pycrmkit
```

must remain sufficient for `import pycrmkit` and in-memory CRM usage.

## Stable optional integration ranges

The package metadata currently declares:

```text
FastAPI        >=0.141,<1
Pydantic       >=2.13,<3
SQLAlchemy     >=2.0,<3
psycopg        >=3.2,<4
Alembic        >=1.16,<2
Django         >=5.2,<6
DRF            >=3.18,<4
```

These ranges describe install compatibility. CI qualification uses
representative current versions within those ranges rather than every possible
combination.

## Django stable qualification

`0.8.0` promotes the qualified Django/DRF release candidate to the stable
`0.8.x` integration line without adding new functional scope.

It is currently qualified with:

```text
Django 5.2 LTS
Python 3.11
Python 3.12
Python 3.13
Django REST Framework 3.18.x
SQLite in-memory repository, migration, admin, transaction and DRF qualification
PostgreSQL 17 reference application E2E
clean installed-wheel Django/PostgreSQL/DRF E2E
```

The stable line qualifies application loading,
Contact/Organization/Relationship repository semantics, packaged migration
`0001_initial`, migration/model drift checking, admin registration, explicit
transaction semantics, the optional facade-backed DRF transport and a real
PostgreSQL-backed reference application.

The `django` extra is also explicitly qualified without DRF installed. The
reference E2E is executed twice: from the source checkout and from a clean wheel
after resetting the PostgreSQL schema.

It does **not** claim full cross-domain Django UnitOfWork/DRF coverage; the
Django persistence adapter remains bounded to Contacts, Organizations and
Relationships in the `0.8.x` line.

## V0.9 Data Operations stable qualification

`0.9.0` promotes the complete V0.9 Data Operations release candidate to a
stable line without adding new functional scope.

The stable V0.9 surface covers:

```text
ExternalIdentity domain/service/repository contract
Memory / SQLAlchemy / Django external-identity persistence
ImportRow / ImportPipeline
mapping / normalization / validation / reports
CSV / JSON / JSONL readers and exporters
deterministic candidate matching and scoring
conflict detection and provenance
conservative transactional Contact merge
activity / relationship reassignment
tag union
custom-field conflict policy
external-identity ownership transfer
duplicate archival
append-only merge audit
source-checkout Data Operations E2E
clean installed-wheel Data Operations E2E
```

The upstream-record key remains `(system, external_id)`.

The stable Data Operations E2E uses `MemoryUnitOfWork` for the complete
cross-capability journey, while the release gate separately retains
PostgreSQL persistence, migrations, FastAPI/PostgreSQL, Django and DRF
regression qualification.

## PostgreSQL

The production-reference persistence, FastAPI E2E and stable Django reference
paths are qualified against:

```text
PostgreSQL 17
```

Other PostgreSQL versions are not claimed by this document unless separately
qualified.

## Persistence schema

The stable `0.9.0` line keeps the SQLAlchemy/Alembic and Django migration
histories explicit and separate.

The currently qualified external-identity schema heads are:

```text
SQLAlchemy / Alembic  0003
Django                0002_external_identity
```

SQLAlchemy-backed applications migrate through:

```bash
pycrmkit-migrate upgrade head
```

Django-backed applications migrate the Django adapter through:

```bash
python manage.py migrate pycrmkit_crm
```

Applications should not create production schemas from ORM metadata helpers or
run migrations implicitly at import/startup time.

## FastAPI compatibility contract

Within `0.7.x`, backward compatibility covers the documented public
integration surface:

```text
request/response schemas
router paths and HTTP methods
pagination shape
ErrorResponse shape
documented error/status mapping
request context headers
OpenAPI generation
create_crm_router(...)
install_error_handlers(...)
```

Internal module layout and undocumented implementation details are not public
compatibility promises.

## Django compatibility contract

Within `0.8.x`, backward compatibility covers the documented stable Django
integration surface:

```text
PyCRMKitDjangoConfig and the pycrmkit_crm app label
Contact / Organization / Relationship Django repositories
packaged Django migration history beginning at 0001_initial
DjangoTransactionBridge explicit commit/rollback semantics
post-commit event publication semantics
Django admin registrations for the three persisted aggregate families
create_drf_router()
DRF serializer/update semantics
DRF pagination shape
DRF domain/request error mapping
X-Actor-ID / X-Correlation-ID propagation
PYCRMKIT_CRM_FACTORY application-owned wiring
```

The stable Django adapter is intentionally bounded to Contacts, Organizations
and Relationships. `0.8.0` does not claim a complete cross-domain Django
`UnitOfWork` or a persistent Django implementation for every PyCRMKit module.

## Data Operations compatibility contract

Within `0.9.x`, backward compatibility covers the documented stable Data
Operations surface:

```text
ExternalIdentity ownership semantics
ImportReader / Mapper / Normalizer / Validator / Deduplicator / Persister protocols
ImportPipeline stage order
ImportReport counter meanings
CSV / JSON / JSONL adapter behavior
DedupSignal names
default deterministic scoring semantics
no_match / review / duplicate / conflict decisions
DedupProvenance evidence shape
explicit primary selection for Contact merge
MergePolicy conservative defaults
duplicate archival rather than physical deletion
activity / relationship / tag / custom-field / external-identity merge behavior
contact.merged audit action
source and clean-wheel Data Operations reference scenario
```

The stable line does **not** promise fuzzy/ML matching, automatic primary
selection, Organization merge execution, or a framework-owned universal
Contact import persistence policy.

## V1 public API freeze candidate

`1.0.0a1` does not replace the current stable `0.9.0` line. It starts the V1
compatibility freeze.

The candidate classification is:

```text
public      intended V1 compatibility commitment
provisional usable/importable but still adjustable before V1 stable
internal    implementation detail with no compatibility promise
```

The executable candidate manifest covers:

```text
root exports
bounded-context package exports
CRM facade namespace methods
typed exception hierarchy
repository protocols and UnitOfWork
CRMConfig / CRMContext fields
built-in event names
DomainEvent serialization envelope
documented external-identity events
public adapter/integration entry points
```

The exact candidate contract is documented in
[PyCRMKit 1.0 Public API Freeze Candidate](../api/1.0-public-api-candidate.md).

ORM models, mapper mechanics, migration implementation modules and concrete
`pycrmkit.facade.*` classes are deliberately not promoted into the V1 public
domain API.

## V1 security and privacy hardening

`1.0.0b1` retains the `1.0.0a1` candidate classification and hardens the
observable security/privacy behavior.

Qualified additions and constraints:

```text
public error serialization redacts sensitive context values
FastAPI/DRF public error bridges use the same redaction
external identity events omit external_id values
webhook subscription/request repr excludes secret-bearing material
crm.webhooks.rotate_secret is an additive public candidate method
webhook HMAC verification can enforce timestamp freshness
merge rejects provenance containing blocking conflicts
public aggregate facades expose lifecycle operations, not generic hard delete
```

The V1 candidate manifest is updated additively for
`crm.webhooks.rotate_secret`.

Security hardening does not promote ORM models, migration internals or concrete
facade implementation classes into the public API.

## Pre-1.0 policy

PyCRMKit remains pre-`1.0.0`. Each stable milestone establishes compatibility
for its documented line, while broader V1 public API freeze remains planned for
`1.0.0`.
