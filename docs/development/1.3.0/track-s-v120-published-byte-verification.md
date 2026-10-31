# Track S - Independent v1.2.0 Published Byte Verification

**Date:** 2026-10-31
**Gate:** S0, AUD-FIX-04 and historical release provenance
**Status:** Verification automation candidate; NO-GO until its own exact-SHA CI passes

## Problem

GitHub Releases reports SHA-256 digests for four artifacts of the stable
`v1.2.0` release, but API metadata alone does not prove that the downloaded
wheel and sdist equal the distributions actually published to PyPI.

The immutable Git annotated tag `v1.2.0` has object
`587d6b806d098b951916b7ad219b08d62ff7ca5c` pointing to commit
`e0ae1c67ccc488918dbef845b799caf7aba3ab70`, independently retrieved
from the GitHub tag-object API.

## Verification procedure

The read-only stdlib script
`scripts/track_s_verify_v120_published_bytes.py` requests:
1. GitHub Release metadata for `v1.2.0`.
2. PyPI's version-scoped JSON metadata for `pycrmkit==1.2.0`.
3. GitHub's `pycrmkit-1.2.0-py3-none-any.whl` and `pycrmkit-1.2.0.tar.gz` bytes.
4. Their corresponding PyPI-hosted distribution bytes.

The job computes SHA-256 from **downloaded bytes** at both hosts,
compares byte equality, compares both hosts' advertised SHA-256 and sizes,
then emits machine-readable JSON and fails closed if any check fails or
a required binary cannot be downloaded. The job uses no secrets, has
read-only repository permissions and does not upload or replace packages.

```bash
python scripts/track_s_verify_v120_published_bytes.py
```

The `Track S - Published v1.2.0 Byte Integrity` workflow archives the
result as `track-s-v120-byte-integrity`, retaining it for 30 days.
The exact run ID, commit SHA, report hash and reviewer decision need to
be appended to the Track S evidence ledger after a successful run.

## Explicit limitations

- Verifying identical bytes is NOT a code security or software supply-chain
  provenance attestation.
- The workflow does not independently rebuild the immutable tagged commit.
- These checks do not authorize merging PR #115 or S0 PR #129.
- Additional S1/RC functional and privacy review remains mandatory.
- No `v1.2.0` tag, manifest, release asset, PyPI version or main branch
  is touched by this verifier.

**Decision: S0 NO-GO until the exact-SHA workflow passes and maintainer signs off.**
