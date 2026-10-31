# Gate S0 - Integration and qualification runbook

**Status:** PROPOSED; do not merge or publish without complete validation.

## Current independent branches and known overlap

| PR | Lot | Head at preparation | Shared files / conflict risk |
|---|---|---|---|
| #117 | AUD-FIX-01 | `f8f6766260f65edfe41f4769dc1434828af0d12b` | `cli/state.py`, `cli/config.py`, `tests/unit/cli/test_cli.py` |
| #127 | AUD-FIX-02 | `98a91dff6985aa9831b863c102e2d036a57ea5d3` | `cli/state.py`, `tests/unit/cli/test_cli.py`, docs configuration |
| #116 | AUD-FIX-03 | `50c7adad8bead9f29db0edc663cc959db24f79d1` | `cli/state.py`, `cli/config.py`, `tests/unit/cli/test_cli.py` |
| #128 | AUD-FIX-04 | see live PR HEAD | source version, live tests, historical gates, docs |

Do not merge GitHub PRs simply because the GitHub API says they are individually
mergeable against the **old** main SHA. Once one is integrated, that assumption
is invalidated for later PRs.

## Required integration approach

1. Create a temporary `integration/track-s-s0` branch from the exact latest
   `main` (no force-push). Protect `v1.2.0`, its release assets and tags.
2. Apply and reconcile changes in **logical order**: 01 (quality and typed
   contracts), 02 (JSON persistence), 03 (explicit backend selection and
   fail-closed safety), 04 (development version and archive separation).
3. Do not simply select one version of `cli/state.py` during a conflict:
   preserve BOTH JSON locking across the full read-modify-write transaction
   and explicit `force_local` routing plus read-only demo safety.
4. In `cli/config.py`, preserve failure on malformed/unreadable YAML and
   strictly typed regex + narrow exception handling; never restore silent
   fallback or process-global actor/database environment mutation.
5. In `tests/unit/cli/test_cli.py`, keep ANSI-normalized help, JSON fixture
   paths, explicit unsafe-seed rejection and ephemeral dashboard cases.
6. Execute isolated security and functionality tests, then full pytest on
   Python 3.11/3.12/3.13, Ruff, mypy and sdist/wheel-installed CLI tests.
7. Check no unexpected `pickle.load/loads` or `copyreg.pickle` remains on
   normal CLI persistence read paths. Test legacy pickle rejection.
8. Verify PostgreSQL non-mutation during `pck seed` without authorization
   and `pck dashboard --demo`; verify unknown config and environment fail
   with no sensitive values in diagnostic output.
9. Verify `1.3.0.dev0` matches source, installed metadata and both CLI
   names. Run historical replay **only** from the immutable 1.2.0 tag.
10. Review warnings, skipped tests, security model and test coverage. Every
    failing test needs a grounded correction; never globally disable a gate.
11. Obtain the maintainer's explicit GO on S0 acceptance criteria
    `AC-S0-01..19`; only then promote code to `main` using a reviewed PR.
12. After merge, rerun all required checks on the **exact main merge SHA**,
    document any rerun and retain evidence. No `1.3.0a1`, rc or stable
    publication is authorized by S0 itself.

## Rollback

Revert the defective PR/merge with a documented impact assessment. Back up
local JSON safely before changes to state schema. Never retag, delete or
overwrite the published `v1.2.0` artifacts. An interrupted local JSON state
write requires inspecting stale lock files and the last committed JSON state.

## Sign-off slots

| Gate | State |
|---|---|
| Source and distribution version integrity | NOT VERIFIED |
| Historical tag/assets unchanged | GitHub metadata observed; independent bytes pending |
| Quality (Ruff/mypy/pytest) exact SHA | NOT VERIFIED |
| JSON storage security/atomicity | NOT VERIFIED |
| Persistent DB no-mutation | NOT VERIFIED |
| PR #115 review and PyPI publication | NOT VERIFIED |
| Final maintainer S0 GO | NOT GRANTED |
