# Changelog

All notable changes to PyCRMKit will be documented in this file.

The project follows Semantic Versioning semantics and PEP 440 version syntax.

## [Unreleased]

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
