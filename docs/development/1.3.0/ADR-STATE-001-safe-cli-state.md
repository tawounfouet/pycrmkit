# ADR-STATE-001 - Versioned JSON for local CLI state

**Status:** PROPOSED / security and CI review pending

**Track:** v1.3.0, AUD-FIX-02, S0

## Context

The local CLI previously loaded untrusted pickle bytes, which may execute Python
code during deserialization, and wrote the store directly without atomic
replacement. The CLI state is a development and demonstration store, not the
canonical business database.

## Decision

Use a **schema-versioned JSON document**, encoded with explicit tagged types
and a trusted allowlist discovered from the installed _MemoryState schema.
Tags in the file never trigger dynamic imports, eval or pickle. Unknown
types, malformed JSON, unknown future versions and invalid objects fail.

Preserve supported domain IDs, UUIDs, Enum values, Decimal, aware dates,
dataclasses, tuples and mappings. Store files use permission mode 0600 and
a bounded maximum size of 16 MiB.

Save by same-filesystem temporary file, flush/fsync and atomic os.replace.
Serialize CLI read-modify-write transactions with an exclusive sibling lock,
so two concurrent CLI writers cannot silently overwrite each other.

## Migration policy

No automatic pickle unpickling. A legacy crm_state.pickle must be archived or
discarded and recreated from a trusted dataset. Do not treat existing pickle
files as safe input. A stale exclusive lock after process interruption must
be reviewed and manually cleared only when no writer is alive.

## Alternatives

- Pickle: rejected for ordinary CLI use because loading may execute code.
- SQLite: viable later, but introduces schema/migrations for a small local demo.
- JSON with import-by-name: rejected because it trusts disk-provided classes.

## Qualifications required

JSON corruption, unknown type/version, no automatic pickle, failure injection
during save, concurrency rejection, complete seeded-dataset roundtrip, three
supported Python versions, Ruff/mypy, wheel/sdist-installed CLI, security
review, and exact-SHA S0 approval.

This ADR and the PR do not constitute proof of gate S0 passage.
