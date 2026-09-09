# Memory Adapter

The official Memory adapter is the reference in-process persistence implementation for tests, examples, CLI prototypes, tutorials, and local development. It is a conformant adapter, not a mock.

## Public components

`0.3.0b1` adds `MemoryPipelineRepository` to the existing Memory repositories.

## Unit of Work

`MemoryUnitOfWork` creates one private transaction snapshot shared by all repositories, including:

```text
activities
contacts
leads
opportunities
pipelines
organizations
relationships
tasks
timeline
tags
custom_fields
audit
```

Leaving without `commit()` rolls back staged changes. Exceptions and explicit `rollback()` also discard uncommitted work.

Mutable aggregates/definitions are copy isolated on save/read.

## Contract qualification

The official Memory repositories execute reusable contract suites. Pipeline qualification covers normalized IDs, ordered stages, transition declarations, terminal outcomes, probability defaults, exact pagination, deterministic ordering, NotFound semantics, and copy isolation.

Opportunity movement loads the Pipeline definition through the same Unit of Work, validates the transition in the domain service, persists the Opportunity mutation, stages Audit/Event records, and only then commits.

The Memory adapter does not claim production concurrency semantics and does not provide SQLAlchemy/PostgreSQL persistence, migrations, durable outbox/retry, or distributed event transport.
