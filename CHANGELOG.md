# Changelog

All notable changes to PyCRMKit will be documented in this file.

The project follows Semantic Versioning semantics and PEP 440 version syntax.

## [Unreleased]

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
