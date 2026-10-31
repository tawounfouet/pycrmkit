# AUD-FIX-06 - Feature tours in installed distributions

**Track:** S1 - Developer Experience
**Status:** IMPLEMENTATION CANDIDATE / NOT QUALIFIED
**Baseline:** S0 candidate 600fddbc29eb2fc0a1ab290e2ea0c03a01791868
**Issue:** #123
**Gate:** S1

## Problem

Previously `pck tours` constructed a relative path with
`Path(__file__).resolve().parents[4] / "examples/feature_tours"`.
That path only works in a source checkout and is absent from an isolated wheel.

## Implementation

The six source tours are included as trusted, allowlisted packaged resources
under `pycrmkit/_feature_tours/*.py.txt`. The canonical resource names match
the historical `examples/feature_tours/*.py` scripts. The repository examples
are lightweight wrappers invoking the same bundled tour entrypoints.

A stdlib resource loader uses `importlib.resources.as_file` and
`SourceFileLoader` to execute the installed Python source resource, even
when distributed through zip-backed package resources. Arbitrary user paths
or filenames are never accepted.

This avoids making six demonstration programs mandatory imports of the
headless CRM core and avoids mypy treating them as public, typed runtime APIs.
The existing `run_all_tours.py` continues to discover source wrappers.
No external network or provider is required by the tours.

## Acceptance tests

- Contract tests ensure the six resources are present and importable.
- Each of the six scripts must execute outside the repository checkout.
- Unknown filenames and path traversal are rejected.
- An independent workflow builds wheel + sdist on Python 3.11/3.12/3.13,
  installs the wheel with `[cli]`, changes to a temporary directory,
  unsets `PYTHONPATH` and executes `pck tours`, `pck demo --tour 1`
  and `pck tours --tour 6`.
- Existing Ruff, mypy, pytest, packaging and adapter checks must remain green
  on the final exact SHA. Verify that both distribution formats include the
  resource files and that sdist-to-wheel installation works.

## Architectural boundaries

The tour assets are trusted code shipped inside the installed package. They
are NOT a generic arbitrary-script execution feature, NOT an agent runtime,
and must not read untrusted pickle state. Tour email providers are mocks:
successful demonstration output is not evidence of external email delivery.

## GO / NO-GO

**NO-GO until actual GitHub CI, artifact inspections and reviewer approval.**
S0 and the immutable v1.2.0 release must remain unchanged. No tag or PyPI
publication is authorized by this implementation.
