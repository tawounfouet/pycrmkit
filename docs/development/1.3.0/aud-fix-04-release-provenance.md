# AUD-FIX-04 - Release identity, provenance and historical qualification

**Status:** IMPLEMENTATION CANDIDATE / S0 NOT QUALIFIED  
**Base:** main at `15140b510506d7822ac38ab36682e1de09ff3b71`  
**Target source version:** `1.3.0.dev0` (PEP 440, no tag or PyPI publication)

## Evidence observed from GitHub (2026-10-31)

- Annotated Git tag: `refs/tags/v1.2.0`
- Annotated Git tag object: `587d6b806d098b951916b7ad219b08d62ff7ca5c`
- Tagged commit: `e0ae1c67ccc488918dbef845b799caf7aba3ab70`
- GitHub stable release: `v1.2.0`, published `2026-10-31T05:45:21Z`, `draft=false`, `prerelease=false`
- GitHub release assets and their SHA256 digests, as reported by GitHub:
  - `pycrmkit-1.2.0-py3-none-any.whl`: `83584d2566b1578558e0c04af564a8e3969f128c5d9db41e96d686f6d3a64350`
  - `pycrmkit-1.2.0.tar.gz`: `01c0b282ca665a99c247c327513831db67aba2c3506248e9997e37dbcf608c9c`
  - `release-manifest-v1.2.0.json`: `802e14aaecedea9e0861a4523721946e0b4d471db8d5015bd22f859cf731dcb5`
  - `SHA256SUMS-v1.2.0.txt`: `1822a3dc3a28ddd414a1628f184d25857e1993d7b1f8d9f70379e4ee53001948`

This is evidence returned by GitHub. Independent download and re-hash of the published
asset bytes is a **separate** qualification step. No GitHub asset was rewritten.

## PyPI evidence and limitation

PR #115, `docs(release): LOT-32-013 publication and audit closeout`, remains **OPEN**
at head `0445f8ab11541ef0c5afd15bf793a2b9d20a7fd6`. It reports successful
PyPI publication at `https://pypi.org/project/pycrmkit/1.2.0/` and Twine checks,
but that is the PR author's evidence, **not independent verification** by this
Track S implementation. Current PyPI state and artifact hashes must be checked
from PyPI or the exact published artifacts before accepting AC-S0-17 and AC-S0-19.

Do not merge PR #115 automatically. Evaluate its documentation against already
published GitHub evidence, source version and current main head; review its checks
and make an explicit merge/close decision.

## Historical archives vs development build

- `tests/compatibility/test_campaign_stable_version_promotion.py` and other
  frozen prepublication tests are original provenance records and must **not**
  be rewritten to force a passing 1.3 development run.
- Frozen 1.2 promotion workflow gates no longer run on every future development PR
  or main push. They are scoped to manual replay. To replay reproducibly, use
  `historical-v1.2.0-tag-replay.yml`, which checks out the immutable
  `v1.2.0` tag and validates its exact SHA.
- `tests/conftest.py` applies explicit `SKIP` markers to the named frozen
  promotion/evidence tests only in development; these are visible in pytest
  summaries. Other compatibility, security and runtime tests still run.
- The historical `scripts/stable_1_2_distribution_manifest.py` stays
  unmodified. It must never be repurposed to inspect `1.3.0.dev0` builds.
- `src/pycrmkit/__about__.py` remains the sole version source, read via
  `[tool.setuptools.dynamic].version` in pyproject.toml.
- Dev wheel/sdist filenames, metadata and CLI version must match `1.3.0.dev0`.
- Published stable `v1.2.0` is not rebuilt, re-tagged, uploaded or overwritten.

## Required next checks before S0

1. Exact candidate SHA build + installed wheel/sdist metadata and CLI on Python 3.11/3.12/3.13.
2. Independent published GitHub artifact download/checksums and PyPI inspection.
3. Changelog, README, release notes and support matrix reconciled with observed facts.
4. Review decision on PR #115 and unmerged branch diffs.
5. Qualify all tests including negative security, Ruff, mypy and relevant distribution CI
   after integrating AUD-FIX-01, AUD-FIX-02 and AUD-FIX-03.
6. Maintainer signs off AC-S0-16..19; until then **NO-GO**.

**No promotion to 1.3.0a1, rc1 or stable is authorized by this document.**
