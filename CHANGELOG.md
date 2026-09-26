# Changelog

All notable changes to PyCRMKit will be documented in this file.

The project follows Semantic Versioning semantics and PEP 440 version syntax.

## [Unreleased]

## [0.7.0a1] - 2026-09-26

### Added
- Optional `fastapi` dependency extra with FastAPI and Pydantic 2.
- Request-scoped `CRMDependency` bridge preserving the application's existing CRM wiring.
- Pydantic request/response schemas for Contacts, Organizations, Relationships, Activities, Tasks, Leads, Opportunities and Timeline.
- Explicit transport-schema conversion into existing PyCRMKit DTOs, Value Objects and typed IDs.
- FastAPI pagination bridge over `OffsetPageRequest` and `Page`.
- Typed `ErrorResponse` preserving public PyCRMKit error code/message/context.
- FastAPI integration tests covering dependency injection, request metadata, pagination, response serialization and facade execution.

### Changed
- Package version advanced from `0.6.0` to `0.7.0a1`.
- FastAPI becomes an opt-in integration extra while the core package remains framework-agnostic.
- Development roadmap advances within the FastAPI line to `0.7.0b1 — Routers`.

### Integration semantics
- `X-Actor-ID` and `X-Correlation-ID` are applied through `CRM.with_context(...)`.
- Missing HTTP context headers preserve the CRM factory's existing context.
- PATCH-like schemas preserve omitted-vs-explicit-clear semantics through domain `UNSET` sentinels.
- Pydantic schemas remain transport objects and are never used as domain Entities.
- No FastAPI router or ORM-direct access path is introduced in this alpha.

### Qualification
- Core `import pycrmkit` is verified not to import FastAPI transitively.
- Schema conversions are exercised against the stable CRM facade.
- Python 3.11/3.12/3.13, Ruff, strict mypy, Docs, Build, PostgreSQL, Migrations, Persistence Qualification and aggregate CI remain green.

### Deferred
- Routers remain scheduled for `0.7.0b1`.
- HTTP status/error mapping and OpenAPI qualification remain scheduled for `0.7.0b2`.
- Example application and PostgreSQL-backed API E2E remain scheduled for `0.7.0rc1`.

## [0.6.0] - 2026-09-26

### Stable
- Promoted the fully qualified `0.6.0rc1` persistence line to stable without adding new persistence feature scope.
- Froze the SQLAlchemy repository, Unit-of-Work, PostgreSQL and Alembic behavior qualified by the release candidate.
- Established migration revision `0002` as the stable `0.6.x` schema head.
- Preserved the stable `0.1`–`0.5` public CRM facade unchanged.

### Qualification
- Stable `0.1`–`0.5` CRM scenario passes on Alembic-migrated PostgreSQL.
- Reusable SQLAlchemy repository contracts pass against PostgreSQL.
- Multi-repository rollback semantics pass against PostgreSQL.
- Migration `0001 → 0002` preserves data and head has no SQLAlchemy metadata drift.
- Installed wheel contains packaged migrations and successfully runs `pycrmkit-migrate upgrade head`, `current`, `check` and the PostgreSQL persistence smoke.
- PostgreSQL 17, Python 3.11/3.12/3.13, Ruff, strict mypy, Docs, Build, Migrations, Persistence Qualification and aggregate CI all pass.

### Changed
- Package version advanced from `0.6.0rc1` to `0.6.0`.
- Persistence Foundation becomes the current stable line.
- Development roadmap advances to `0.7.0 — FastAPI Integration`.

### Deferred
- FastAPI, Django and Data Operations remain later roadmap lines.
- Durable distributed outbox/claiming semantics remain outside the current `0.6.x` persistence contract.

## [0.6.0rc1] - 2026-09-26

### Added
- Dedicated Persistence Qualification CI gate over live PostgreSQL 17.
- End-to-end qualification of the stable 0.1–0.5 CRM facade on an Alembic-migrated PostgreSQL database.
- PostgreSQL execution of the reusable SQLAlchemy repository conformance suite.
- Explicit multi-repository rollback qualification against PostgreSQL.
- Installed-wheel smoke in a clean virtual environment using packaged migrations and PostgreSQL.
- Alembic revision `0002 — align repository reference semantics`.

### Changed
- Package version advanced from `0.6.0b3` to `0.6.0rc1`.
- Migration head advanced from `0001` to `0002`.
- Lead and Opportunity contact/organization references remain indexed IDs but no longer impose cross-aggregate database foreign-key preconditions.
- Webhook Delivery subscription references remain indexed IDs but no longer impose a repository-level subscription existence precondition.
- Package development classifier advanced from Alpha to Beta for the persistence release-candidate line.

### Persistence semantics
- Repository protocols remain the source of truth for adapter behavior.
- Database foreign keys remain for persistence ownership relationships, including Tag Assignment → Tag and nested Communication/Webhook attempt rows.
- Cross-aggregate identifiers are not strengthened into backend-only existence rules.
- PostgreSQL ownership-FK violations remain translated into backend-neutral PyCRMKit errors.

### Migration qualification
- Fresh PostgreSQL databases upgrade from `base` to `0002`.
- Existing `0.6.0b3` databases upgrade from `0001` to `0002` with data preserved.
- Head matches SQLAlchemy metadata with no detected drift.
- Downgrade-to-base / re-upgrade lifecycle remains qualified.

### Release-candidate qualification
- Stable CRM Core, Activity/Timeline, Sales, Communication and Eventing/Webhooks flows persist and reload through PostgreSQL.
- SQLAlchemy repository conformance passes on PostgreSQL.
- Installed wheel can run packaged `pycrmkit-migrate upgrade head`, `current` and `check` against PostgreSQL before executing a persistence smoke.
- Ruff, strict mypy, documentation, build, aggregate CI, PostgreSQL, Migrations and Python 3.11/3.12/3.13 test gates pass together.

### Deferred
- `0.6.0` stable is the promotion milestone for the qualified persistence foundation and should not add new persistence feature scope.

## [0.6.0b3] - 2026-09-26

### Added
- Alembic migration environment, configuration and immutable `0001` persistence baseline.
- Optional `migrations` dependency group for Alembic + PostgreSQL migration tooling.
- Dedicated PostgreSQL migration CI covering empty-database upgrade, downgrade/re-upgrade and schema drift.
- Verified adoption path for existing `0.6.0b2` schemas via parity check followed by `alembic stamp 0001`.
- Explicit destructive baseline downgrade policy and migration immutability rules.

### Changed
- Package version advanced from `0.6.0b2` to `0.6.0b3`.
- Production schema evolution now uses versioned Alembic revisions instead of relying on `Base.metadata.create_all(...)`.
- Immutable files under `migrations/versions/` are excluded from Ruff formatting and are instead compiled and executed in migration CI.

### Migration semantics
- Fresh databases upgrade from `base` to `head` at revision `0001`.
- Revision `0001` matches current SQLAlchemy metadata with no detected drift.
- Baseline downgrade to `base` is supported but destructive.
- Existing `0.6.0b2` databases with verified schema parity can be stamped at `0001` without data loss.
- Released migration revisions are immutable; future schema changes require new revisions.

### Qualification
- Migration lifecycle passes against live PostgreSQL 17.
- Direct `alembic check` reports no new upgrade operations.
- PostgreSQL persistence, Ruff, strict mypy, docs, build and aggregate CI remain green.
- General tests pass on Python 3.11, 3.12 and 3.13.

### Deferred
- Full persistence release-candidate qualification, including installed-wheel + PostgreSQL smoke, remains scheduled for `0.6.0rc1`.

## [0.6.0b2] - 2026-09-26

### Added
- Optional `postgresql` dependency group backed by psycopg 3.
- Dedicated live PostgreSQL 17 GitHub Actions qualification workflow.
- PostgreSQL schema, constraint and index introspection tests.
- Production-reference round trips for Unicode, timezone-aware datetimes, Decimal, JSON and Custom Fields.
- Concurrent normalized-Tag uniqueness qualification using independent SQLAlchemy Sessions.
- Backend-neutral SQLAlchemy/PostgreSQL commit error translation.

### Changed
- Package version advanced from `0.6.0b1` to `0.6.0b2`.
- Tag persistence now stores the normalized domain name explicitly and protects it with a named database uniqueness constraint.
- Tag assignments now enforce `(tag_id, entity_kind, entity_id)` uniqueness at the database layer.
- SQLAlchemy Unit-of-Work commit failures now translate SQLSTATE-backed database failures into PyCRMKit persistence exceptions.

### PostgreSQL semantics
- SQLSTATE 23505 maps to `DuplicateError`.
- Foreign-key, not-null and check violations map to typed `RepositoryError` codes.
- Serialization failures and deadlocks receive stable repository error codes.
- SQL text and bound parameter values are excluded from public error context.

### Qualification
- Live PostgreSQL 17 job passes.
- Ruff, strict mypy, docs, package build and aggregate CI pass.
- General tests remain green on Python 3.11, 3.12 and 3.13.

### Deferred
- Versioned schema evolution and upgrade/downgrade qualification remain scheduled for `0.6.0b3 — Alembic / Migrations`.
- Full persistence release-candidate qualification remains scheduled for `0.6.0rc1`.

## [0.6.0b1] - 2026-09-26

### Added
- SQLAlchemy Unit of Work owning one shared Session across all persistence repositories.
- Explicit commit, rollback, rollback-on-exit and rollback-on-exception semantics.
- Post-commit domain-event staging compatible with the established Memory adapter behavior.
- Transaction qualification for Lead conversion, Contact merge foundations, Pipeline transitions and bulk-write foundations.
- SQLAlchemy Sales facade E2E coverage for Lead conversion and terminal pipeline movement.
- SQLAlchemy persistence/UoW documentation and release notes.

### Changed
- Package version advanced from `0.6.0a2` to `0.6.0b1`.
- SQLAlchemy transaction ownership now lives at the Unit-of-Work boundary; repository adapters continue to avoid internal commits.
- `SQLAlchemyUnitOfWork` and `SessionFactory` are exported from `pycrmkit.storage.sqlalchemy`.

### Transaction semantics
- All repositories in one UoW share the same SQLAlchemy Session.
- Uncommitted context exit and exceptions roll back pending changes.
- Explicit rollback discards pending writes while keeping the UoW usable.
- Domain events publish only after a successful database commit.
- Subscriber failure after commit cannot roll back committed state.
- Repeated commit on the same transaction is rejected.

### Qualification
- Ruff, strict mypy, docs, package build and aggregate CI pass.
- Tests pass on Python 3.11, 3.12 and 3.13.
- Stable Memory adapter and 0.1–0.5 compatibility tests remain green.

### Deferred
- PostgreSQL production-reference integration, constraints/index validation and concurrency tests remain scheduled for `0.6.0b2`.
- Alembic migrations remain scheduled for `0.6.0b3`.
- Full persistence qualification remains scheduled for `0.6.0rc1`.

## [0.6.0a2] - 2026-09-26

### Added
- Session-scoped SQLAlchemy repository adapters for Contacts, Organizations, Relationships, Activities, Tasks, Leads, Opportunities and Pipelines, satisfying the repository-adapter milestone defined by the implementation plan.
- SQLAlchemy adapters for the additional persisted 0.1–0.5 boundaries: Tags, Custom Fields, Timeline, Audit, Communication, webhook subscriptions and webhook delivery history.
- Explicit Domain ↔ ORM mappers preserving typed identifiers, value objects, deterministic ordering, pagination, uniqueness/idempotency semantics and normalized repository errors.
- Timeline persistence metadata required to round-trip the exact typed-ID class carried by generic EntityReference values.
- Correct composite persistence identity for versioned Custom Field definitions using (id, schema_version).
- Reusable repository conformance execution against isolated SQLite SQLAlchemy sessions plus targeted Communication adapter qualification.

### Changed
- Package version advanced from `0.6.0a1` to `0.6.0a2`.
- SQLAlchemy repository adapters are exported from `pycrmkit.storage.sqlalchemy`.
- Repository writes remain session-scoped and do not commit internally; transaction ownership is reserved for the upcoming SQLAlchemy Unit of Work.

### Qualification
- Ruff, mypy, docs, package build and aggregate CI pass.
- Repository/adapter tests pass on Python 3.11, 3.12 and 3.13.
- Existing Memory adapter and stable 0.1–0.5 compatibility tests remain green.

### Deferred
- SQLAlchemy Unit of Work and transaction orchestration remain scheduled for `0.6.0b1`.
- PostgreSQL integration/concurrency qualification remains scheduled for `0.6.0b2`.
- Alembic migrations remain scheduled for `0.6.0b3`.
- Full PostgreSQL persistence qualification remains scheduled for `0.6.0rc1`.

## [0.6.0a1] - 2026-09-26

### Added
- Optional SQLAlchemy 2.x adapter foundation with deterministic declarative metadata.
- Explicit domain/ORM mapping protocol and functional mapper helper.
- SQLAlchemy persistence models covering CRM Core, Activity/Timeline persistence primitives, Sales, Communication/Audit, and Eventing/Webhook delivery state.
- Normalized persistence structures for contact points, organization domains/addresses, pipeline stages/transitions, communication recipients/references, and webhook attempts.
- SQLAlchemy foundation tests and release notes.

### Compatibility
- SQLAlchemy remains optional; importing the PyCRMKit core does not require the ORM.
- Repository adapters, SQLAlchemy Unit of Work, PostgreSQL qualification, and Alembic migrations remain deferred to later 0.6.x prereleases.

## [0.5.0] - 2026-09-26

### Stable
- Promoted the fully qualified `0.5.0rc1` Eventing & Webhooks line to stable without adding new functional scope.
- Froze the documented `0.5.x` event registry, serialization, trace propagation, webhook registration, signing, delivery, retry/backoff, idempotency, dead-letter, history, and automatic post-commit bridge surfaces.
- Preserved stable `0.1`–`0.4` root/facade contracts and the shallow package root.
- Qualified the complete Contact create → `contact.created` → match → sign → deliver → retry → history path as the stable Eventing/Webhooks integration contract.
- Confirmed Memory Unit-of-Work post-commit sequencing supports subscriber-owned follow-up transactions against committed state.

### Changed
- Package version advanced from `0.5.0rc1` to `0.5.0`.
- Candidate API and webhook documentation now reflect the stable `0.5.x` compatibility promise.
- Development roadmap now advances to `0.6.0a1 — SQLAlchemy Foundation`.

### Deferred
- Production SQLAlchemy/PostgreSQL persistence, durable cross-process outbox/claiming, distributed delivery coordination, FastAPI, Django, and data operations remain later milestones.


## [0.5.0rc1] - 2026-09-26

### Added
- Automatic EventBus-to-webhook bridge for registered public event types.
- Default automatic delivery of committed CRM domain events to matching active webhook subscriptions.
- `webhook_auto_delivery=False` opt-out while preserving explicit `crm.webhooks.deliver(...)`.
- Release-candidate E2E scenario covering Contact creation → `contact.created` → subscription matching → canonical serialization → HMAC signing → 503 retry scheduling → 204 retry success → delivery/attempt history.
- Installed-wheel smoke of the automatic webhook E2E path.

### Changed
- Package version advanced from `0.5.0b2` to `0.5.0rc1`.
- Memory Unit of Work now releases the store transaction after committed state is published but before synchronous post-commit subscribers run, allowing subscriber-owned follow-up UoWs against committed state.
- Repeated commit on the same Memory Unit of Work is rejected explicitly.
- The `0.5.x` Eventing & Webhooks facade/configuration surface enters compatibility freeze pending stable promotion.

### Compatibility
- Stable `0.1`–`0.4` root/facade contracts remain unchanged.
- Explicit webhook delivery/retry/history APIs from `0.5.0b2` remain available alongside automatic bridging.

### Deferred
- `0.5.0` stable is a qualification/promotion milestone with no planned new Eventing/Webhooks feature scope.
- SQLAlchemy/PostgreSQL production persistence, durable cross-process outbox/claiming and distributed delivery coordination remain later milestones.


## [0.5.0b2] - 2026-09-26

### Added
- Provider-neutral `WebhookTransport`, request/response DTOs, and a standard-library HTTP transport.
- Default transport policy blocking non-public destinations and redirects unless private-network delivery is explicitly enabled.
- Versioned HMAC-SHA256 webhook signing plus constant-time verification helper.
- Deterministic exponential `WebhookRetryPolicy` with explicit retryable HTTP status policy.
- Persistent `WebhookDelivery` state keyed idempotently by subscription + event and append-only `WebhookDeliveryAttempt` history.
- Delivery states for pending, scheduled retry, success, and dead-letter outcomes.
- `crm.webhooks.deliver(...)`, `retry_due()`, `deliveries(...)`, and `attempts(...)`.
- Memory delivery repository and Unit-of-Work participation.
- Unit, contract, Memory, facade E2E, local HTTP-boundary, and installed-wheel smoke qualification.

### Changed
- Package version advanced from `0.5.0b1` to `0.5.0b2`.
- Webhook subscriptions now carry a secret-safe signing secret, generated when omitted.
- Canonical serialized event payloads are retained in delivery state so scheduled retries do not depend on the original in-process event object.

### Retry policy
- Timeouts/network errors, HTTP 408, 425, 429, and 5xx are retryable.
- Other 3xx/4xx responses are terminal.
- Exhausted retryable failures enter dead-letter state.

### Deferred
- Automatic CRM EventBus → webhook delivery wiring remains scheduled for `0.5.0rc1`.
- Production-grade database claiming/concurrency semantics remain part of the later persistence milestones.


## [0.5.0b1] - 2026-09-26

### Added
- First-class `WebhookSubscription` with typed ID, validated HTTP(S) endpoint, registered event-type set, active/disabled lifecycle, and exact matching.
- Backend-neutral `WebhookSubscriptionRepository` plus official copy-isolated Memory adapter and reusable repository contract tests.
- `WebhookSubscriptionService` with register, disable, list and active-event matching operations.
- Transactional `crm.webhooks.register(...)`, `crm.webhooks.disable(...)` and `crm.webhooks.list(...)` facade APIs.
- Optional `EventRegistry` injection into `CRM` / `CRM.memory()` so custom registered public events can participate in webhook registrations.
- Privacy-conscious audit entries for registration and first disable, without introducing webhook-management domain events.
- Installed-package smoke coverage for registration, event filtering and disable behavior.

### Changed
- Package version advanced from `0.5.0a2` to `0.5.0b1`.
- Memory Unit of Work now includes webhook subscription persistence.
- Event-driven context views preserve the configured event registry.

### Deferred
- No outbound HTTP request is performed in this milestone.
- HMAC signing, transport, retries, backoff, delivery logs, idempotent external delivery and dead-letter handling remain scheduled for `0.5.0b2`.


## [0.5.0a2] - 2026-09-26

### Added
- `CRMContext.from_event(...)` for deterministic child-operation trace context.
- `CRM.with_event(...)` for event-triggered facade mutations sharing the same backend and event bus.
- Actor inheritance, stable correlation-root propagation, and direct `causation_id` assignment across multi-hop event chains.
- Correlation fallback to the parent event ID when an upstream correlation ID is absent.
- Validation that CRM/event causation identifiers are typed `EventId` values.
- Unit and installed-package smoke coverage for root → child → grandchild causal propagation.

### Changed
- Package version advanced from `0.5.0a1` to `0.5.0a2`.
- Event documentation now defines the causal propagation semantics required by later webhook delivery.

### Deferred
- Webhook registrations remain scheduled for `0.5.0b1`.
- HMAC signing, retries, backoff, delivery logging and dead-letter handling remain scheduled for `0.5.0b2`.


## [0.5.0a1] - 2026-09-25

### Added
- Version-aware `EventDefinition` and `EventRegistry` for exact public event type/schema pairs.
- Fresh `default_event_registry()` containing the 41 stable v1 events emitted by the `0.1`–`0.4` domains.
- Registry-governed `EventSerializer` with deterministic compact JSON serialization and validated deserialization.
- Canonical `contact.created` v1 serialization fixture for integration compatibility.
- Unit/smoke coverage for registration, duplicate detection, version resolution, unknown schemas, canonical JSON, and installed-package round trips.

### Changed
- Package version advanced from `0.4.0` to `0.5.0a1`.
- Events documentation now distinguishes flexible internal event creation from the registered public serialization boundary.

### Deferred
- Correlation/causation integration remains scheduled for `0.5.0a2`.
- Webhook registrations, HMAC signing, retry/backoff, delivery logs, idempotent external delivery and dead-letter behavior remain later `0.5.x` milestones.


## [0.4.0] - 2026-09-25

### Stable
- Promoted the fully qualified `0.4.0rc1` Communication line to stable without adding new business scope.
- Froze the documented `0.4.x` `crm.email` facade, provider-neutral email contracts, normalized lifecycle events, Memory Communication persistence, and Communication Timeline projection.
- Qualified templates, stdlib SMTP, optional Resend, provider-result persistence, callback idempotency, out-of-order delivery history, and communication-history E2E as one integrated release line.
- Preserved the stable `0.1`–`0.3` public surfaces and shallow root exports.
- Finalized the architectural decision that Communication projects directly into Timeline rather than creating duplicate email Activity entities.

### Changed
- Package version advanced from `0.4.0rc1` to `0.4.0`.
- Communication documentation now reflects the complete stable scope and removes prerelease deferrals.
- Installed-wheel smoke now exercises transactional `crm.email` send, delivery callback ingestion, history and Timeline projection.


## [0.4.0rc1] - 2026-09-25

### Added
- Transactional crm.email send/history namespace with direct and templated email support.
- Memory persistence for communication intents, attempts, CRM records and append-only delivery events.
- Normalized email.queued, email.sent, email.delivered, email.opened, email.clicked, email.bounced and email.failed events.
- Provider callback replay idempotency by external event ID and provider-message correlation.
- Communication Timeline projections and contact/organization communication-history queries.
- Out-of-order callback protection for current CommunicationRecord delivery state.
- Communication-history release-candidate E2E qualification.

### Changed
- Package version advanced from 0.4.0b2 to 0.4.0rc1.
- The 0.4 Communication feature scope is now frozen pending stable promotion.


## [0.4.0b2] - 2026-09-24

### Added
- Optional official Resend SDK adapter implementing the existing `EmailProvider` contract.
- `ResendConfig` with secret-safe representation and provider naming.
- Request mapping for sender, recipients, subject, text/HTML content, PyCRMKit intent header, and Resend idempotency options.
- Provider message ID capture plus selected response/request metadata.
- Normalized Resend API/client failures without persisting provider error messages.
- Serialized SDK API-key set/send/restore behavior to prevent cross-instance credential leakage.
- Network-free Resend adapter tests covering request mapping, idempotency, provider IDs, error mapping, invalid responses, and credential restoration.

### Changed
- Package version advanced from `0.4.0b1` to `0.4.0b2`.
- Resend is governed through the optional `resend` extra; the base package remains runtime dependency-free.

### Deferred
- Delivery/open/click/bounce event ingestion, Communication persistence/history projection, and release-candidate integration remain scheduled for `0.4.0rc1`.

## [0.4.0b1] - 2026-09-24

### Added
- Provider-neutral `EmailTemplate` and runtime-checkable `TemplateRenderer` contracts.
- Optional strict `Jinja2TemplateRenderer` behind the `email` extra, with HTML autoescaping.
- Standard-library `SMTPEmailProvider` with plain, STARTTLS, and implicit TLS connection modes.
- MIME text/HTML construction, generated Message-ID, PyCRMKit intent/idempotency headers, partial-recipient metadata, and normalized SMTP failure mapping.
- Network-free SMTP adapter tests plus installed-package qualification.

### Changed
- Package version advanced from `0.4.0a2` to `0.4.0b1`.
- Jinja2 is governed as an optional email dependency; the base runtime remains dependency-free.

### Deferred
- Resend remains scheduled for `0.4.0b2`.
- Delivery/open/click/bounce events and Communication history integration remain scheduled for `0.4.0rc1`.

## [0.4.0a2] - 2026-09-24

### Added
- Runtime-checkable `EmailProvider.send(...)` protocol and normalized `EmailProviderResult`.
- Immutable provider-neutral `EmailMessage`.
- `EmailDeliveryService` mapping provider acceptance/failure to `DeliveryAttempt`.
- Provider message ID, provider metadata, failure-code, contract, service, and installed-package qualification.

### Changed
- Package version advanced from `0.4.0a1` to `0.4.0a2`.

### Deferred
- Concrete SMTP/Resend providers and templates remained outside this alpha.

## [0.4.0a1] - 2026-09-24

### Added
- Provider-independent `CommunicationIntent`, `DeliveryAttempt`, and `CommunicationRecord` domain foundation.
- Typed Communication identifiers, channels, directions, lifecycle statuses, addresses, recipients, and content.
- Explicit separation between communication intent, transport attempt, and CRM relationship-history record.

### Changed
- Package version advanced from `0.3.0` to `0.4.0a1`.

### Deferred
- Provider contracts, concrete providers, templates, and downstream delivery events remained outside this alpha.

## [0.3.0] - 2026-09-24

### Stable
- Promoted the fully qualified `0.3.0rc1` Sales Foundation to stable without adding new business scope.
- Froze the documented `0.3.x` facade contract for Leads, Opportunities and Pipelines while preserving the stable `0.1` and `0.2` surfaces.
- Qualified atomic/idempotent Lead conversion, Pipeline initial-stage defaults, invalid-transition rejection, won/lost outcomes, Sales Events and transactional Audit as one integrated domain line.
- Qualified the release on Python 3.11, 3.12 and 3.13 plus installed-wheel smoke of both won and lost sales paths.
- Finalized stable `0.3` API documentation and release notes.

### Changed
- Package version advanced from `0.3.0rc1` to `0.3.0`.
- The former candidate Sales compatibility document is now the stable `0.3.x` compatibility contract.

## [0.3.0rc1] - 2026-09-24

### Added
- Release-candidate end-to-end qualification for the complete Sales Foundation across Lead capture, qualification, conversion, Pipeline movement, invalid-transition rejection, won/lost outcomes, Events and Audit.
- Explicit candidate `0.3` public API document freezing `crm.leads.create/qualify/disqualify/convert`, `crm.opportunities.create/move`, and `crm.pipelines.define/get/list`.
- Qualification of the documented Sales event set: `lead.created`, `lead.qualified`, `lead.disqualified`, `lead.converted`, `opportunity.created`, `opportunity.stage_changed`, `opportunity.won`, and `opportunity.lost`.
- Installed-wheel smoke coverage for both won and lost sales paths plus disqualification, conversion replay idempotency, invalid transition rejection, and stable Activity/Task/Timeline compatibility.
- `0.3.0rc1` release notes and candidate documentation.

### Changed
- Package version advanced from `0.3.0b2` to `0.3.0rc1`.
- The `0.3` Sales facade surface enters compatibility freeze pending stable promotion.
- No new business feature scope is introduced by the release candidate.

### Deferred
- `0.3.0` stable remains a qualification/promotion step with no planned new Sales feature scope.
- Sales Timeline projection, durable outbox/delivery, SQLAlchemy/PostgreSQL, Communication, FastAPI, Django and later integrations remain outside `0.3.x`.

## [0.3.0b2] - 2026-09-23

### Added
- Atomic `LeadConversionService` coordinating Lead and Opportunity repositories inside one Unit of Work.
- Public `crm.leads.convert(...)` with optional name, value/currency, pipeline, expected-close date, owner, and idempotency key.
- Conversion provenance linking a converted Lead to exactly one Opportunity plus canonical request fingerprint.
- Domain-level idempotent replay: same key/equivalent request returns the existing Opportunity without duplicate events or audit; conflicting replay raises `ConflictError`.
- Pipeline-aware conversion entering the initial Stage and applying its default probability.
- Post-commit `opportunity.created` and `lead.converted` events with transactional, privacy-conscious audit history.
- Unit, facade, rollback, post-commit transport-retry, end-to-end, compatibility-smoke, and installed-package qualification.

### Changed
- Package version advanced from `0.3.0b1` to `0.3.0b2`.
- `crm.leads` gains the additive `convert(...)` method while `get` and `list` remain outside the public facade.
- Lead `converted` state may now retain conversion provenance needed for deterministic replay.

### Deferred
- Sales-wide end-to-end compatibility freeze and release-candidate hardening remain scheduled for `0.3.0rc1`.
- Durable event delivery/outbox, retries, and dead-letter handling remain part of the later Eventing & Webhooks roadmap.

## [0.3.0b1] - 2026-09-09

### Added
- Configurable `Pipeline` and ordered `Stage` definitions with normalized identifiers, finite Decimal default probabilities, terminal outcomes, and explicit `StageTransition` rules.
- `PipelineTransitionPolicy` and typed `InvalidStageTransition` failures for rejected commercial stage movement.
- Backend-neutral `PipelineRepository` / `PipelineService`, official copy-isolated `MemoryPipelineRepository`, and Pipeline participation in `MemoryUnitOfWork`.
- Transactional `crm.pipelines.define(...)`, `crm.pipelines.get(...)`, and `crm.pipelines.list(...)` facade operations.
- Public `crm.opportunities.move(...)` with transition-policy validation, `stage_entered_at`, current-stage duration, stage-default probability, and terminal outcome mapping.
- Post-commit `pipeline.created`, `opportunity.stage_changed`, `opportunity.won`, `opportunity.lost`, and `opportunity.cancelled` events with privacy-conscious audit history.
- Unit, adapter, Unit-of-Work, facade, end-to-end, public API, and installed-package smoke qualification for Pipeline/Stage integration.

### Changed
- Package version advanced from `0.3.0a2` to `0.3.0b1`.
- `crm.opportunities` now exposes additive pipeline movement through `move(...)`; direct `mark_won`, `mark_lost`, `get`, and `list` remain outside the public facade.
- Pipeline terminal semantics use pipeline-local `StageOutcome` values that are mapped to `OpportunityStatus` at the Opportunity service boundary.

### Deferred
- Public and idempotent Lead-to-Opportunity conversion remains scheduled for `0.3.0b2`; `crm.leads.convert` remains intentionally absent.

## [0.3.0a2] - 2026-09-09

### Added
- First-class `Opportunity` aggregate with typed `OpportunityId` and commercial lifecycle states `open`, `won`, `lost`, and `cancelled`.
- Opportunity commercial context including required Contact, optional Organization, opaque pipeline/stage references, Decimal estimated value/currency/probability, expected close date, and owner.
- Backend-neutral `OpportunityQuery`, `OpportunityRepository`, and `OpportunityService` contracts.
- Official copy-isolated `MemoryOpportunityRepository` and Opportunity participation in the shared `MemoryStore` / `MemoryUnitOfWork` transaction.
- Deliberately narrow transactional `crm.opportunities.create(...)` facade with post-commit `opportunity.created` events and privacy-conscious audit entries.
- Unit, repository, Unit-of-Work, facade, end-to-end, public API, and package-smoke qualification for Opportunities.

### Changed
- Package version advanced from `0.3.0a1` to `0.3.0a2`.
- `CRM` gains the additive `opportunities` namespace while preserving the existing `0.1`, `0.2`, and Lead contracts.

### Deferred
- Configurable Pipelines/Stages and public `crm.opportunities.move(...)` remained scheduled for `0.3.0b1`.
- Public/idempotent Lead-to-Opportunity conversion remains scheduled for `0.3.0b2`.

## [0.3.0a1] - 2026-09-08

### Added
- Immutable Decimal-only `Money` primitive with required normalized three-letter currency and explicit rejection of float/non-finite persistence values.
- First-class `Lead` aggregate with typed `LeadId`, required `ContactId`, optional `OrganizationId`, normalized source, and lifecycle states `new`, `open`, `contacted`, `qualified`, `disqualified`, and `converted`.
- Explicit Lead domain transitions plus backend-neutral `LeadQuery`, `LeadRepository`, and `LeadService`.
- Official copy-isolated `MemoryLeadRepository` and Lead participation in the shared `MemoryStore` / `MemoryUnitOfWork` transaction.
- Deliberately narrow `crm.leads` facade exposing `create`, `qualify`, and `disqualify`, with post-commit `lead.created`, `lead.qualified`, and `lead.disqualified` events plus privacy-conscious audit entries.
- Reusable Lead repository contract suite covering state fidelity, filters, deterministic `created_at DESC, id ASC` ordering, exact pagination, NotFound semantics, and terminal-state persistence.
- Unit, adapter, Unit-of-Work, facade, end-to-end, public API, and installed-package smoke qualification for Money and Leads.
- Money, Leads, repository-contract, Memory adapter, and `0.3.0a1` release documentation.

### Changed
- Package version advanced from `0.2.0` to `0.3.0a1`.
- `CRM` gains the additive `leads` namespace while stable `0.1` and `0.2` root/facade contracts remain unchanged.

### Deferred
- Opportunities remain scheduled for `0.3.0a2`.
- Pipelines and Stages remain scheduled for `0.3.0b1`.
- Public/idempotent Lead-to-Opportunity conversion remains scheduled for `0.3.0b2`; `crm.leads.convert` is intentionally absent in this alpha.

## [0.2.0] - 2026-09-07

### Stable
- Promoted the qualified Activity, Task and Timeline release candidate to the stable `0.2.x` line without adding new business scope.
- Froze the documented `0.2` public API for `crm.activities`, `crm.tasks` and read-only `crm.timeline` while preserving the stable `0.1` root imports and CRM Core namespaces.
- Qualified historical Activity business-time semantics, explicit Task lifecycle transitions, transactional Timeline projection, idempotent replay, deterministic ordering, exact offset pagination and half-open temporal filtering.
- Qualified the complete release on Python 3.11, 3.12 and 3.13 plus an installed-wheel `CRM.memory()` Activity/Task/Timeline smoke path.
- Finalized stable `0.2` API documentation and release notes.

### Changed
- Package version advanced from `0.2.0rc1` to `0.2.0`.
- The `0.2` candidate compatibility document is now the stable `0.2.x` compatibility contract.

## [0.2.0rc1] - 2026-09-07

### Added
- Release-candidate integration coverage for Contact + Organization + imported historical Activity history.
- Full Task lifecycle qualification across `created`, `started`, `completed`, `reopened` and `cancelled` projections.
- Multi-entity Timeline consistency checks, exact offset pagination, half-open time-window filtering, source-transaction rollback and replay idempotency qualification.
- Candidate `0.2` public API freeze preserving the `0.1` root exports and adding `activities`, `tasks` and read-only `timeline` facade namespaces.
- Installed-wheel smoke path covering historical Activity, Task lifecycle and Timeline pagination.
- `0.2.0rc1` release notes.

### Changed
- Package version advanced to `0.2.0rc1`.
- Activity, Task and Timeline behavior entered compatibility freeze pending stable qualification.

## [0.2.0b1] - 2026-09-07

### Added
- Immutable `TimelineEntry` projections with typed `TimelineEntryId`, source `EventType` / `EventId`, source aggregate reference, business occurrence timestamp, title/summary, CRM references, actor/correlation context, and privacy-conscious metadata.
- Backend-neutral `TimelineRepository` contract with idempotent append semantics and deterministic `occurred_at DESC, kind ASC, id ASC` ordering.
- Domain-event-driven `TimelineProjector` and pure projection helpers for `activity.created` and meaningful Task lifecycle events (`created`, `started`, `completed`, `cancelled`, `reopened`).
- Atomic timeline projection inside the same Unit of Work as the originating mutation; external EventBus dispatch remains post-commit.
- Official `MemoryTimelineRepository`, timeline persistence in `MemoryStore`, and Timeline participation in `MemoryUnitOfWork`.
- Read-only `crm.timeline` facade with `for_contact`, `for_organization`, `get`, kind/event filters, date-window filters, and exact offset pagination.
- Timeline unit, adapter, idempotency, ordering, filtering, configuration, and Contact/Organization end-to-end tests.
- Timeline overview and repository-contract documentation.

### Changed
- Package version advanced to `0.2.0b1`.
- `CRM` now exposes the additive `timeline` namespace while preserving the frozen root exports.
- Activity/Task domain events now also feed the customer-facing read model when they represent meaningful relationship history; audit remains a separate system mutation history.

## [0.2.0a2] - 2026-09-07

### Added
- First-class `Task` aggregate with typed `TaskId`, explicit lifecycle status, ordered priority, due dates, owner/assignee context, generic CRM references, source/external identity, metadata, and lifecycle timestamps.
- Explicit `start`, `complete`, `cancel`, and `reopen` transitions; lifecycle status is deliberately excluded from generic `TaskUpdate` patches.
- Backend-independent `TaskQuery`, typed `TaskUpdate`, `TaskRepository`, and `TaskService` with create/get/update/lifecycle/list operations.
- Official copy-isolated `MemoryTaskRepository` plus reusable Task repository contract suite.
- Task participation in the shared `MemoryUnitOfWork`, including commit and rollback semantics.
- Transactional `crm.tasks` facade namespace with `task.created`, `task.updated`, `task.started`, `task.completed`, `task.cancelled`, and `task.reopened` events plus privacy-conscious audit entries.
- End-to-end Contact + Task lifecycle + Events/Audit scenario.
- Tasks documentation and repository-contract specification.

### Changed
- Package version advanced to `0.2.0a2`.
- `CRM` now exposes the additive `tasks` namespace while the stable `0.1` root exports remain unchanged.

## [0.2.0a1] - 2026-09-07

### Added
- First-class `Activity` aggregate with typed `ActivityId`, eight base interaction types, optional direction, occurrence time, duration, source/external reference, participants, generic entity references, and metadata.
- `ActivityParticipant` value object backed by generic `EntityReference` targets without aggregate loading.
- Backend-independent `ActivityQuery`, typed `ActivityUpdate`, `ActivityRepository`, and `ActivityService` with `log/get/update/list` operations.
- Official copy-isolated `MemoryActivityRepository` plus reusable Activity repository contract suite.
- Activity participation in the shared `MemoryUnitOfWork`, including commit and rollback semantics.
- Transactional `crm.activities` facade namespace with `activity.created` / `activity.updated` events and privacy-conscious audit entries.
- End-to-end Contact + Organization + Activity + Events/Audit scenario.
- Activities documentation and repository-contract specification.

### Changed
- Package version advanced to `0.2.0a1`.
- `CRM` now exposes the new `activities` namespace while preserving the frozen `0.1` root imports.

## [0.1.0] - 2026-09-06

### Stable
- Promoted the CRM Core release candidate to the first stable `0.1.x` line without adding new domain scope.
- Froze the documented `0.1` public API: root imports, CRM facade namespaces, repository/UoW semantics, typed IDs/value objects, and versioned Domain Event envelope.
- Qualified the complete CRM Core on Python 3.11, 3.12, and 3.13.
- Hardened public API smoke tests and the installed-wheel smoke path to execute `CRM.memory()` and a real Contact create/get round-trip.
- Finalized stable documentation, compatibility policy, and release notes.

### Changed
- Package version advanced from `0.1.0rc1` to `0.1.0`.
- Project development classifier advanced from Pre-Alpha to Alpha.

## [0.1.0rc1] - 2026-09-06

### Added
- High-level transactional `CRM` facade and fully wired `CRM.memory()` constructor.
- Public `CRMConfig` and `CRMContext` with actor, correlation, and causation propagation.
- Facade namespaces for Contacts, Organizations, Relationships, Tags, Custom Fields, Events, and read-only Audit history.
- Automatic facade-level domain events and privacy-conscious audit entries for CRM Core mutations.
- Independent Events/Audit feature toggles while preserving domain-service reuse.
- Shallow root imports: `CRM`, `CRMConfig`, `CRMContext`, and `__version__`.
- End-to-end Memory scenario covering Contact → Organization → Relationship → Tags → Custom Fields → Events/Audit.
- Candidate `0.1` public API compatibility document and facade documentation.

### Changed
- Package version advanced to `0.1.0rc1`.
- Quickstart now uses the integrated `CRM.memory()` path as the recommended entry point.

## [0.1.0b4] - 2026-09-06

### Added
- Immutable, schema-versioned `DomainEvent` envelope with typed `EventId` and validated dotted `EventType`.
- JSON-compatible payload/metadata validation, recursive immutability, and stable envelope serialization/deserialization.
- Fixture-based `contact.created` v1 event compatibility test.
- Synchronous `InProcessEventBus` with subscribe, unsubscribe, decorator registration, deterministic handler ordering, and explicit failure propagation.
- Append-only `AuditEntry`, `AuditRepository`, `AuditService`, and privacy-conscious event-to-audit context bridge.
- Official `MemoryAuditRepository` plus reusable Audit repository contract suite.
- Audit participation in `MemoryUnitOfWork` so required audit history commits or rolls back with domain mutations.
- Post-commit event staging in `MemoryUnitOfWork`; rollback and uncommitted exit discard pending events.
- Explicit behavior that subscriber failures after commit cannot roll back already committed MemoryStore state.
- Events and Audit documentation.

## [0.1.0b3] - 2026-09-06

### Added
- Official `MemoryContactRepository`, `MemoryOrganizationRepository`, `MemoryRelationshipRepository`, `MemoryTagRepository`, and `MemoryCustomFieldRepository`.
- Copy-on-save and copy-on-read isolation so in-memory behavior matches persistent adapter expectations.
- Shared `MemoryStore` committed-state container.
- Backend-independent `UnitOfWork` protocol and explicit-commit `MemoryUnitOfWork`.
- Atomic multi-repository commit, explicit rollback, exception rollback, and rollback-on-exit without commit.
- Explicit rejection of nested/concurrent Memory UoWs on the same store.
- Official Memory adapter execution of all five reusable repository contract suites.
- Adapter-specific tests for mutation isolation and transaction semantics.
- Memory adapter documentation.

## [0.1.0b2] - 2026-09-06

### Added
- Generic `EntityReference` core primitive for cross-domain entity targeting without aggregate loading.
- Normalized `Tag`, `TagAssignment`, `TagRepository`, and `TagService` lifecycle with duplicate-assignment protection.
- Versioned Custom Field definitions with stable keys, immutable field types, sequential `schema_version`, and historical revision lookup.
- Supported custom-field types: string, text, integer, decimal, boolean, date, datetime, email, phone, URL, enum, multi-enum, reference, and JSON.
- Typed custom-field validation including normalized contact-point values, timezone-aware datetimes, enum options, reference-kind restrictions, and defensive JSON validation.
- Current custom-field values recording the schema revision that validated them.
- Reusable Tag and Custom Field repository contract suites executed against test-only reference repositories.
- Tags and Custom Fields documentation and repository-contract specifications.

## [0.1.0b1] - 2026-09-06

### Added
- Strongly typed `RelationshipId`, `RelationshipEndpoint`, and open-ended `RelationshipType`.
- Typed Contact/Organization endpoints supporting Contact↔Organization, Contact↔Contact, and Organization↔Organization links.
- Directional relationship aggregate with role, title, primary flag, metadata, and explicit validity intervals.
- Half-open `[valid_from, valid_until)` activity semantics and idempotent relationship ending.
- Backend-independent `RelationshipQuery` and typed `RelationshipUpdate`.
- `RelationshipRepository` protocol with get/find/save/end/search contracts.
- `RelationshipService` create/get/update/end/search operations.
- Third reusable repository contract suite, executed against a test-only reference repository.
- Relationships documentation and repository-contract specification.

## [0.1.0a3] - 2026-09-06

### Added
- Strongly typed `OrganizationId` and organization lifecycle status.
- `OrganizationDomain` with DNS/IDNA normalization and `OrganizationAddress` value object.
- Organization aggregate with legal/trading identity, display-name resolution, registration/tax identifiers, domains, addresses, owner, source, metadata, and archival invariants.
- Backend-independent `OrganizationQuery` and typed `OrganizationUpdate`.
- `OrganizationRepository` protocol with get/find/save/archive/search contracts.
- `OrganizationService` create/get/update/archive/search operations.
- Second reusable repository contract suite, executed against a test-only reference repository.
- Organizations documentation and repository-contract specification.

## [0.1.0a2] - 2026-09-06

### Added
- Strongly typed `ContactId` and Contact lifecycle status.
- `ContactEmail`, `ContactPhone`, and `Address` value objects with explicit normalization.
- Verification-state and primary contact-point foundations.
- Contact aggregate with identity, archival, metadata, owner, source, and timestamp invariants.
- Backend-independent `ContactQuery`, `OffsetPageRequest`, and exact `Page` semantics.
- `ContactRepository` protocol with get/find/save/archive/search contracts.
- `ContactService` create/get/update/archive/search operations and typed `ContactUpdate`.
- First reusable repository contract suite, executed against a test-only reference repository.
- Contacts documentation and repository-contract specification.

## [0.1.0a1] - 2026-09-06

### Added
- Immutable typed UUID identifiers with `UUIDId` / `EntityId`.
- Injectable `IDFactory` protocol and `UUID4Factory` default implementation.
- `Clock`, `SystemClock`, and controllable `FixedClock` primitives.
- Strict timezone-aware UTC normalization through `as_utc`.
- Entity identity/equality conventions and timestamped entities.
- Immutable `ValueObject` convention.
- Typed, machine-readable PyCRMKit exception hierarchy.
- Unit tests and public core-primitives documentation.

## [0.0.3] - 2026-09-06

### Added
- CI workflows for linting, typing, tests, documentation, package build, and release checks.
- MkDocs documentation foundation.
- Release-check and smoke-test scripts.

## [0.0.2] - 2026-09-06

### Added
- `src/` package layout.
- Package metadata and typed package marker.
- Pytest, Ruff, mypy, coverage, and pre-commit configuration.
- Initial package smoke tests.

## [0.0.1] - 2026-09-06

### Added
- Repository governance and project bootstrap.
- MIT license.
- Contribution, security, editor, Git, and Python-version conventions.
