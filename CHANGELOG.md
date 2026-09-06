# Changelog

All notable changes to PyCRMKit will be documented in this file.

The project follows Semantic Versioning semantics and PEP 440 version syntax.

## [Unreleased]

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
