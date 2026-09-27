# Migrations

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 6 - Persistence & Integrations**.

Chapter 24 established PostgreSQL as the production-reference persistence
backend. A working current schema is not enough for a real application, however:
production databases already contain data and must evolve from one released
version to the next.

PyCRMKit uses Alembic for that lifecycle.

The stable migration architecture is:

~~~text
SQLAlchemy Models
        |
        | current desired metadata
        v
Base.metadata
        |
        +-------------------+
                            |
Alembic revision history   |
        |                   |
        v                   |
0001 -> 0002 -> 0003 -------+
        |
        v
existing PostgreSQL database
        |
        v
alembic_version
~~~

The central rule is:

> Released migration revisions are immutable history. Change the schema by
> adding a new reviewed revision, never by rewriting a revision already shipped.

## What you will learn

You will learn to:

- install PyCRMKit migration tooling;
- understand the packaged Alembic environment;
- understand the current migration chain;
- distinguish SQLAlchemy metadata from migration history;
- upgrade an empty database to head;
- inspect the current revision;
- detect schema drift;
- understand the role of the alembic_version table;
- adopt a pre-Alembic database safely with stamp;
- understand the 0001 baseline;
- understand 0002 repository-reference alignment;
- understand 0003 external identities;
- understand upgrade and downgrade boundaries;
- understand destructive downgrade policy;
- understand data-preserving upgrade qualification;
- understand migration immutability;
- understand reviewed autogeneration;
- understand installed-wheel migration qualification;
- prepare for framework integrations such as FastAPI.

## 1. Install the migration extra

~~~bash
pip install "pycrmkit[migrations]"
~~~

The migrations extra installs SQLAlchemy, Alembic and psycopg.

Migration support is optional just like the SQLAlchemy/PostgreSQL adapters.

## 2. The installed CLI is pycrmkit-migrate

PyCRMKit exposes:

~~~text
pycrmkit-migrate
~~~

through the project scripts configuration.

The command operates on migration files packaged inside PyCRMKit.

## 3. Database configuration uses PYCRMKIT_DATABASE_URL

The default environment variable is:

~~~text
PYCRMKIT_DATABASE_URL
~~~

Example:

~~~bash
export PYCRMKIT_DATABASE_URL='postgresql+psycopg://crm:secret@localhost:5432/crm'
~~~

A database URL may also be supplied explicitly through the CLI.

## 4. The packaged script location is stable

The migration CLI configures Alembic with:

~~~text
pycrmkit.storage.sqlalchemy:migrations
~~~

rather than requiring callers to know a checkout-specific filesystem path.

This is important for installed-wheel operation.

## 5. The stable CLI surface

The packaged command supports:

~~~text
upgrade
downgrade
current
check
stamp
history
~~~

Examples:

~~~bash
pycrmkit-migrate upgrade head
pycrmkit-migrate current
pycrmkit-migrate check
pycrmkit-migrate history
~~~

## 6. upgrade applies revision operations

~~~bash
pycrmkit-migrate upgrade head
~~~

moves the database from its current migration revision to the current head by
executing each required upgrade function in order.

## 7. current reads database migration state

~~~bash
pycrmkit-migrate current
~~~

reports the revision recorded in the database's Alembic version state.

It answers:

~~~text
Which migration revision has this database applied?
~~~

## 8. check compares model metadata and migration state

~~~bash
pycrmkit-migrate check
~~~

asks Alembic whether current SQLAlchemy metadata would generate new migration
operations.

A clean result is part of the no-drift contract.

## 9. history describes revision history

~~~bash
pycrmkit-migrate history
~~~

shows the revision chain.

The current stable chain is:

~~~text
0001  persistence baseline
  |
  v
0002  align repository reference semantics
  |
  v
0003  external identities
~~~

## 10. 0003 is the current migration head

The migration qualification suite expects:

~~~text
head = 0003
~~~

The alembic_version table contains 0003 after a successful upgrade to head.

## 11. SQLAlchemy metadata and migration history are different things

SQLAlchemy metadata describes:

~~~text
what the schema should look like now
~~~

Alembic revisions describe:

~~~text
how an existing schema gets from an earlier state to that current state
~~~

Both are necessary.

## 12. create_all is not migration history

This:

~~~python
Base.metadata.create_all(engine)
~~~

can create currently declared tables in a fresh database.

It cannot tell an existing production database how to transform version 0001
into 0003 while preserving data.

## 13. Alembic is the production schema-evolution mechanism

Production evolution is:

~~~text
existing schema
      |
      v
revision operations
      |
      v
next schema
~~~

not:

~~~text
drop everything
create current metadata
~~~

## 14. env.py binds Alembic to Base.metadata

The packaged Alembic environment sets:

~~~text
target_metadata = Base.metadata
~~~

This lets Alembic compare the migration-built database against the SQLAlchemy
adapter's current model definitions.

## 15. Type drift is compared

The environment enables:

~~~text
compare_type = True
~~~

A changed column type can therefore appear in drift detection.

## 16. Server-default drift is compared

The environment also enables:

~~~text
compare_server_default = True
~~~

Server-default differences are part of schema comparison.

## 17. Online migrations use a live connection

In online mode, Alembic builds an engine from configuration and executes
migrations through a live database connection.

The migration environment uses NullPool for this migration engine.

## 18. Offline migrations use the configured URL

Offline mode configures the dialect from the database URL and enables literal
binding for generated SQL.

Both online and offline paths use the same Base.metadata target.

## 19. Missing database configuration is rejected

The migration environment and CLI require either:

~~~text
PYCRMKIT_DATABASE_URL
~~~

or an explicitly supplied SQLAlchemy URL.

The placeholder driver URL in alembic.ini is not treated as a real target.

## 20. 0001 is the persistence baseline

Revision 0001 has:

~~~text
revision = "0001"
down_revision = None
~~~

It creates the persistence schema introduced by the 0.6.x SQLAlchemy/PostgreSQL
line.

## 21. The baseline is intentionally large

0001 creates the original persistence tables, constraints and indexes for the
bounded contexts that existed when the persistence foundation was frozen.

A baseline establishes the first Alembic-tracked state.

## 22. Existing pre-Alembic databases need adoption, not recreation

The 0.6.0b2 PostgreSQL schema existed before Alembic history was introduced.

Those databases already had the schema represented by 0001.

Running 0001 create operations over those tables would be wrong.

## 23. stamp records history without running schema operations

For a verified pre-Alembic database:

~~~bash
pycrmkit-migrate stamp 0001
~~~

records the migration revision without executing 0001 upgrade operations.

## 24. stamp does not validate schema correctness by itself

Stamp means:

~~~text
record this revision
~~~

not:

~~~text
prove the database structurally matches this revision
~~~

Schema parity must be verified before stamping an existing database.

## 25. Drift must be reconciled before adoption

The stable migration guidance explicitly requires a pre-Alembic schema to match
the expected baseline before it is stamped.

A drifted database should not be relabeled as 0001 merely to make Alembic happy.

## 26. 0002 aligns repository reference semantics

Revision 0002 has:

~~~text
revision = "0002"
down_revision = "0001"
~~~

Its purpose is to remove cross-aggregate foreign keys that were stronger than
the backend-neutral repository contracts.

## 27. 0002 removes five foreign keys

The upgrade removes persistence-only existence requirements for:

~~~text
Lead.contact_id
Lead.organization_id
Opportunity.contact_id
Opportunity.organization_id
WebhookDelivery.subscription_id
~~~

## 28. 0002 preserves the reference columns

The migration removes the foreign-key constraints, not the actual IDs.

The reference columns and relevant indexes remain available.

## 29. 0002 is a semantic migration

The reason for the change is repository-contract alignment.

PostgreSQL should not impose cross-aggregate existence requirements absent from
the domain repository protocols.

## 30. 0002 downgrade restores the stricter 0001 policy

The downgrade recreates those foreign keys.

This is structurally reversible, but callers still need to consider whether
their current data satisfies the older stricter constraints.

## 31. 0003 adds external identities

Revision 0003 has:

~~~text
revision = "0003"
down_revision = "0002"
~~~

It adds persistence for the Data Operations external-identity feature.

## 32. 0003 creates pycrmkit_external_identities

The table contains:

~~~text
id
system
external_id
entity_type
entity_id
metadata
created_at
updated_at
~~~

## 33. 0003 adds provider-key uniqueness

It creates:

~~~text
uq_pycrmkit_external_identities_system_external_id
~~~

over:

~~~text
system
external_id
~~~

matching the ExternalIdentity ownership invariant.

## 34. 0003 adds an entity lookup index

It also creates:

~~~text
ix_pycrmkit_external_identities_entity
~~~

over:

~~~text
entity_type
entity_id
~~~

## 35. 0003 downgrade removes only its own additions

Downgrading 0003 drops the external-identity index and table, returning schema
control to 0002.

A migration revision should own the inverse of the changes it introduces.

## 36. Fresh databases upgrade through the full chain

For an empty PostgreSQL database:

~~~bash
pycrmkit-migrate upgrade head
pycrmkit-migrate current
pycrmkit-migrate check
~~~

The database reaches 0003 rather than bypassing migration history through
create_all.

## 37. The alembic_version table tracks applied revision state

After upgrade to head, the qualification suite reads:

~~~text
SELECT version_num FROM alembic_version
~~~

and expects:

~~~text
0003
~~~

## 38. Head must match current SQLAlchemy metadata

After upgrading an empty database to head, the migration suite compares the live
schema with Base.metadata.

Expected result:

~~~text
schema diffs = []
~~~

## 39. No drift is a release gate

The stable requirement is:

~~~text
migration-built PostgreSQL schema
            ==
current SQLAlchemy metadata
~~~

If model changes are made without a matching migration, the gate should fail.

## 40. Migration drift can occur in both directions

Examples include:

~~~text
model column exists but migration never creates it
migration creates constraint no longer declared by metadata
type differs
server default differs
index or FK policy diverges
~~~

The qualification prevents silent divergence.

## 41. alembic check complements explicit metadata comparison

The project uses direct metadata comparison in tests and also runs Alembic
checks as part of migration qualification.

These provide overlapping protection against accidental drift.

## 42. Upgrade from previous released state is tested with data

The migration suite explicitly upgrades from revision 0001 to current head while
a real Contact is already persisted.

## 43. Existing data must survive forward migration

The test:

~~~text
upgrade -> 0001
persist Contact
upgrade -> head
reload Contact
~~~

expects the same Contact after migration.

## 44. Data-preserving upgrade tests matter

An empty-database upgrade can pass even when a migration accidentally damages
existing rows.

A previous-version fixture makes preservation part of the contract.

## 45. 0001 foreign keys are verified before 0002 removal

The migration suite first upgrades to 0001 and introspects the cross-aggregate
foreign keys.

It verifies that the expected old constraints really exist at that historical
revision.

## 46. Head verifies those foreign keys are absent

The same test upgrades to head and verifies the five constraints are gone.

This proves both historical state and current intended state.

## 47. Historical migration behavior matters

A migration test should not only inspect the final schema.

It should also prove that intermediate released revisions represent the schema
they claim to represent.

## 48. Downgrade to base is implemented

The migration chain supports:

~~~bash
pycrmkit-migrate downgrade base
~~~

for qualification and disposable environments.

## 49. Baseline downgrade is destructive

Downgrading all the way to base drops the PyCRMKit persistence schema.

The project explicitly documents this as destructive.

## 50. Destructive downgrade is not the default production rollback strategy

Production rollback should generally prefer:

~~~text
application rollback
        +
forward corrective migration
~~~

unless a particular revision documents a data-safe downgrade.

## 51. Why forward fixes are often safer

Once newer application versions have written new data shapes, an older schema
may no longer be able to represent all current data.

Blind downgrade can therefore destroy or invalidate information.

## 52. Downgrade correctness is still tested

Even though baseline downgrade is destructive, CI verifies:

~~~text
head
  |
  v
base
  |
  v
head
~~~

on a disposable database.

## 53. Re-upgrade after base must return to no-drift head

After destructive downgrade, the suite upgrades to current head again and
expects:

~~~text
current = 0003
schema diffs = []
~~~

## 54. Released revisions are immutable

Once a revision ships, do not edit its upgrade/downgrade operations to match a
new model.

Create another revision.

## 55. Why revision immutability matters

If revision 0001 changes after one environment already applied the original
0001, then:

~~~text
database A "0001"
        !=
database B "0001"
~~~

The version identifier would stop uniquely describing schema history.

## 56. Migration history is a release artifact

A released revision is part of compatibility history just like a published API
contract.

Changing it retroactively breaks reproducibility.

## 57. New model change means new revision

After changing persistence models:

~~~bash
alembic revision --autogenerate -m "describe schema change"
~~~

creates a candidate migration.

The new revision is then reviewed and committed.

## 58. Autogenerate is a starting point, not authority

PyCRMKit documentation explicitly requires every autogenerated operation to be
reviewed.

Alembic can detect structural differences, but it cannot infer every business
or data-migration intention safely.

## 59. Review upgrade and downgrade separately

A good migration review asks:

~~~text
Does upgrade produce the intended next schema?
Does it preserve existing data?
Does downgrade make sense?
Is downgrade destructive?
Do constraints match repository contracts?
Are indexes preserved?
~~~

## 60. Review data compatibility, not only DDL syntax

A syntactically correct migration can still fail production assumptions.

Examples:

~~~text
new NOT NULL column with existing rows
unique constraint over dirty historical data
type narrowing
renamed column interpreted as drop + add
FK introduced against unresolved references
~~~

These require explicit migration design.

## 61. Revision files are excluded from Ruff formatting

The project excludes:

~~~text
src/pycrmkit/storage/sqlalchemy/migrations/versions
~~~

from Ruff processing.

Reviewed migration operations remain stable rather than being reformatted
automatically after release.

## 62. Migration Python is still executed and qualified

Exclusion from formatting does not mean migration code is ignored.

The revisions are imported and executed by Alembic against PostgreSQL in CI.

## 63. Packaged migration assets matter

The installable package includes the migration environment and template assets
needed to run migrations outside the repository checkout.

## 64. The CLI builds Alembic configuration programmatically

migration_config configures:

~~~text
script_location
sqlalchemy.url
~~~

for the packaged environment.

Consumers do not need an editable source checkout.

## 65. Installed-wheel migration qualification is explicit

The Persistence Qualification workflow:

~~~text
builds wheel
creates clean venv
installs wheel with migration dependencies
runs pycrmkit-migrate upgrade head
runs current
runs check
runs PostgreSQL smoke
~~~

## 66. Why wheel qualification is stronger than source-tree qualification

A source checkout may contain files accidentally omitted from package metadata.

A clean wheel install proves the artifact contains the migration resources a
real consumer receives.

## 67. Migration packaging is part of release correctness

If Python domain code ships but Alembic revisions or templates are missing, the
production persistence release is incomplete.

The installed-wheel gate prevents that class of failure.

## 68. Migration commands operate against explicit database state

A migration command should be treated as an infrastructure change.

It should target a known database URL and run with normal deployment controls.

## 69. current and check are useful deployment diagnostics

Before and after upgrade, operators can use:

~~~bash
pycrmkit-migrate current
pycrmkit-migrate check
~~~

to verify revision state and drift.

## 70. history gives the expected chain

~~~bash
pycrmkit-migrate history
~~~

helps verify which upgrades exist between a deployed revision and head.

## 71. A safe deployment sequence is explicit

A practical schema deployment sequence is:

~~~text
identify current revision
        |
        v
backup / recovery readiness
        |
        v
run migration qualification in CI
        |
        v
upgrade target environment
        |
        v
verify current
        |
        v
verify check / smoke
        |
        v
deploy compatible application
~~~

Exact operational ordering can depend on a future migration's compatibility
requirements.

## 72. Migration ordering and application ordering can matter

A backwards-compatible additive migration may support:

~~~text
schema first -> app second
~~~

A breaking schema change may require expand/migrate/contract staging.

PyCRMKit's current three revisions are explicit history, not a universal
zero-downtime deployment algorithm.

## 73. Expand/contract is a useful future pattern

For changes that cannot be deployed atomically with one app release:

~~~text
expand schema
      |
      v
deploy code supporting old + new
      |
      v
migrate data
      |
      v
stop using old shape
      |
      v
contract schema
~~~

A future migration must document such compatibility requirements if needed.

## 74. Data migration and schema migration may differ

Alembic revisions can contain both DDL and controlled data transformation, but
the safety properties must be reviewed explicitly.

The current 0002 and 0003 changes are primarily structural.

## 75. Migration revision IDs form deterministic history

Current PyCRMKit history is intentionally simple:

~~~text
0001
0002
0003
~~~

Each revision points to exactly one previous revision.

## 76. The current chain is linear

There are no migration branches or merge revisions in the stable current
history.

~~~text
0001 -> 0002 -> 0003
~~~

## 77. down_revision defines lineage

Each revision states its predecessor:

~~~text
0001 -> None
0002 -> 0001
0003 -> 0002
~~~

Alembic uses this lineage to determine upgrade/downgrade order.

## 78. Migration head and database current are separate concepts

~~~text
migration head
    = newest revision shipped by package

database current
    = newest revision applied to that database
~~~

An environment can legitimately be behind head before deployment.

## 79. Upgrade calculates the path between those states

If a database is at 0001 and package head is 0003:

~~~text
0001
  |
  +--> apply 0002
  |
  +--> apply 0003
  |
  v
0003
~~~

## 80. Stamp changes version state without executing the path

That is why stamp should only be used when operators already know the physical
schema corresponds to the revision being recorded.

## 81. Migration tests reset PostgreSQL schema completely

The migration test fixture drops and recreates the public schema around each
test.

This ensures historical migration tests start from deterministic state.

## 82. Migration qualification uses PostgreSQL

The test suite requires:

~~~text
PYCRMKIT_DATABASE_URL
~~~

and is marked for PostgreSQL qualification.

Migration behavior is production-schema behavior and should be tested on the
production-reference database.

## 83. Migration head is part of persistence compatibility

A PyCRMKit package version implies not just Python APIs but a known migration
history and head.

Persistence deployment should therefore treat package and migration versioning
as one release concern.

## 84. Minimal fresh-database workflow

~~~bash
export PYCRMKIT_DATABASE_URL='postgresql+psycopg://crm:secret@localhost:5432/crm'

pycrmkit-migrate upgrade head
pycrmkit-migrate current
pycrmkit-migrate check
~~~

Expected current stable head:

~~~text
0003
~~~

## 85. Minimal pre-Alembic adoption workflow

For a verified 0.6.0b2-compatible schema:

~~~bash
pycrmkit-migrate stamp 0001
pycrmkit-migrate current
pycrmkit-migrate check
pycrmkit-migrate upgrade head
~~~

Do not stamp a drifted database merely to silence migration errors.

## 86. Minimal revision-development workflow

After changing SQLAlchemy models:

~~~bash
alembic revision --autogenerate -m "describe schema change"
~~~

Then review the generated revision and qualify:

~~~bash
pycrmkit-migrate upgrade head
pycrmkit-migrate current
pycrmkit-migrate check
~~~

## Common mistakes

### Using create_all on an existing production database

create_all is not a versioned schema-evolution strategy.

### Editing 0001, 0002 or 0003 after release

Released revisions are immutable.

### Running stamp without verifying schema parity

Stamp records history; it does not repair drift.

### Treating alembic_version as proof the schema is correct

A revision label can be wrong if an operator stamped or manually altered the
database incorrectly.

### Ignoring alembic check

Model/migration drift can otherwise reach release.

### Testing only empty-database upgrade

Existing data must also survive forward migrations.

### Assuming downgrade is always safe

The baseline downgrade is explicitly destructive.

### Using downgrade as the default production rollback

Prefer forward correction unless a revision documents a safe downgrade path.

### Trusting autogenerate without review

Autogenerate cannot understand all semantic/data compatibility requirements.

### Adding a foreign key because two columns look related

Migration constraints must still match repository/domain ownership semantics.

### Forgetting package qualification

Migrations must work from the wheel consumers install, not only from source.

## Testing migrations

Fresh-install tests should cover:

~~~text
empty database -> upgrade head
current revision == 0003
application tables match Base.metadata
schema diffs == []
~~~

Historical-upgrade tests should cover:

~~~text
upgrade to old revision
insert representative data
upgrade to head
verify data survives
verify schema matches metadata
~~~

Semantic-history tests should cover:

~~~text
old constraint exists at old revision
new revision removes or adds intended constraint
unrelated schema remains intact
~~~

Downgrade tests should cover:

~~~text
head -> intended downgrade target
document whether data loss occurs
re-upgrade where supported
~~~

Drift tests should cover:

~~~text
compare_type
compare_server_default
Alembic metadata comparison
alembic check
~~~

Packaging tests should cover:

~~~text
build wheel
install clean environment
migration CLI available
packaged revisions available
upgrade head
current
check
PostgreSQL smoke
~~~

## What you learned

You can now explain:

- why migration history differs from current SQLAlchemy metadata;
- the packaged pycrmkit-migrate command;
- PYCRMKIT_DATABASE_URL;
- upgrade/current/check/stamp/history/downgrade;
- the 0001 -> 0002 -> 0003 chain;
- 0001 as persistence baseline;
- 0002 as repository-reference semantic alignment;
- 0003 as External Identity persistence;
- alembic_version tracking;
- schema drift detection;
- safe pre-Alembic adoption;
- data-preserving historical upgrades;
- destructive downgrade policy;
- revision immutability;
- reviewed autogeneration;
- installed-wheel migration qualification.

## LEVEL 6 in progress

The Persistence & Integrations path now contains:

~~~text
22 Memory Adapter      ✅
23 SQLAlchemy          ✅
24 PostgreSQL          ✅
25 Migrations          ✅
26 FastAPI             ← NEXT
~~~

Persistence evolution is now complete conceptually:

~~~text
Domain
  |
  v
Repository contracts
  |
  v
SQLAlchemy
  |
  v
PostgreSQL
  |
  v
Alembic versioned evolution
~~~

The next step is to expose this application layer over HTTP without leaking
persistence or framework concerns into the domain.

## Next

The next chapter is **26 - FastAPI**.

The integration architecture becomes:

~~~text
HTTP Request
    |
    v
FastAPI Router / Schema
    |
    v
PyCRMKit CRM facade
    |
    v
Unit of Work
    |
    v
PostgreSQL
~~~

The next learning question is:

> How does PyCRMKit expose CRM capabilities through FastAPI while keeping
> Pydantic schemas, dependency injection, HTTP status codes and OpenAPI concerns
> outside the domain model?
