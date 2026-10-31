# PyCRMKit v1.3.0 - Track S Gate S0: qualification snapshot

**Date:** 2026-10-31  
**Branch:** `integration/track-s-s0`  
**Pull request:** [#129](https://github.com/tawounfouet/pycrmkit/pull/129)  
**State:** **NO-GO / open draft / not merged**

## 2026-11-01 audit update (historical exact-SHA evidence)

- PR #129 integration HEAD `600fddbc29eb2fc0a1ab290e2ea0c03a01791868` had **74/74 successful check runs**, zero pending or failed, including Ruff, mypy, pytest 3.11/3.12/3.13, PostgreSQL 17 no-mutation, wheel/sdist and GitGuardian. This is historical evidence for that SHA only.
- GitHub v1.2.0 release asset digest metadata matches `aud-fix-04-release-provenance.md`; independent downloaded-byte hashing and PyPI checksums remain unverified.
- PR #115 remains open and requires explicit reconciliation.
- GitHub PR #129 had zero submitted reviews. Branch protection endpoint returned 403; absence of returned rulesets is not proof of absent protection.
- Separate hardening branch `audit/track-s-s0-closeout-hardening` adds production seed/reset engine-denial regression coverage. **This new branch is not qualified by the earlier 74/74 result.**
- The previous queue/pending language below is preserved as a dated historical snapshot, not current CI status.
- **NO-GO** for merge/release until new exact-SHA checks, independent provenance verification and explicit maintainer approval.

## Trust boundaries and evidence levels

Do not treat a green check on an earlier commit as evidence for a newer SHA.
Qualify the **exact final PR SHA**, and again the actual merge SHA if eventually
merged. GitHub checks currently show a large queue of pending CI jobs for
successive PR commits, so no full integrated pass is yet available.

## Observed historical CI, not final acceptance

- Standalone AUD-FIX-01 PR #117 at `55a17140c7eff05aeb5bae1a90c46329b1fa3fe2`:
  Ruff, mypy, pytest 3.11, 3.12 and 3.13 passed. Historical v1.2
  source-identity gates still failed, prompting separate AUD-FIX-04 scope.
- Early integrated S0 candidate `39202daa36405c8066c715496f3b9e84c3477aa4`:
  foundation CI reported **1,273 passed, 66 skipped, 8 warnings** on Python
  3.13, and its mypy job succeeded. Its Ruff job did **not** pass due to
  an import-block formatting issue since corrected.
- GitGuardian passed on the integration branch after a scanner-triggering
  *synthetic* test value was replaced and the branch was rebuilt from its
  immutable main parent. This is not a security-audit signoff.
- GitHub v1.2.0 annotated tag and its four release asset digests were
  recorded in `aud-fix-04-release-provenance.md`. Independent PyPI
  verification and cross-registry hashes remain outstanding.

## New regression contracts added since that baseline

| Area | Enforced contract | Evidence required |
|---|---|---|
| CLI state codec | Versioned JSON; no pickle; exact dataclass fields; reject duplicate keys, nonfinite numbers, invalid root collections and forged typed-ID repository entries | Full seeded roundtrip, corruption/fuzz tests, exact SHA Python matrix |
| State mutations | Same per-path lock across read/modify/write and reset existence/confirmation/delete; atomic replace, no partial writes | Concurrent writer/reset, interrupted replace, file permissions |
| Persistent DB | Implicit seed and dashboard demo never create a persistent engine; production seed/reset refused | Live isolated PostgreSQL 17 no-mutation CI |
| Diagnostics | Doctor fails on explicitly configured inaccessible backend; no exception-based password leak | CLI and doctor negative tests, log inspection |
| Package identity | `1.3.0.dev0` source, metadata, CLI and wheel/sdist align; frozen v1.2.0 gates manual-only | Installed-wheel/sdist matrix 3.11/3.12/3.13 |
| Historical truth | Tagged v1.2 source and assets unchanged; prepublication docs clearly labelled historical | Independent GitHub and PyPI registry inspection and checksum audit |

## Exact required gate before GO

1. Wait for a complete test result **on the final integrated SHA**, not
   an earlier successful branch or cherry-picked result.
2. Full Ruff, mypy, pytest 3.11/3.12/3.13 and appropriate framework,
   adapter, migration, packaging and security checks must be green.
3. PostgreSQL 17 / demo no-mutation workflow must succeed with zero
   unexpected DB engine access, unchanged table inventory and unchanged
   sentinel row.
4. Confirm no failures or new unexplained skips in tests; any declared
   archive-only skips must be tied explicitly to immutable v1.2 evidence.
5. Validate full JSON seeded-dataset roundtrip, persistence corruption
   rejection, lock failure/recovery and production-mode denial.
6. Verify GitHub stable release asset SHA256 from actual downloaded
   bytes; separately verify PyPI publication and distribution checksums.
7. Decide how to close/merge PR #115, without rewriting historical release
   artifacts. Maintain the ADR and all acceptance evidence.
8. Obtain explicit gate S0 maintainer GO before merging PR #129 into main.
9. If merged, re-qualify the exact main merge SHA. No v1.3 version
   promotion or publication is implied.

## Preservation and rollback

`main` and annotated `v1.2.0` remain untouched by draft PR #129. Do
not force-update or rewrite those refs. For an S0 failure, repair the
isolated integration branch and require fresh exact-SHA validation.
