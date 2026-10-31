# AUD-FIX-09 - Track S Release Evidence Ledger

**Captured:** 2026-10-31 (GitHub API snapshot, not continuous monitoring)
**Status:** CANDIDATE EVIDENCE / NO-GO
**Scope:** Source v1.3.0.dev0, baseline v1.2.0; no authorized new release.

## 1. Source and CI evidence by exact SHA

| Deliverable | Exact Git commit SHA | Workflow runs successful | Check runs | Governance state |
|---|---|---|---|---|
| S0 integration PR #129 | `600fddbc29eb2fc0a1ab290e2ea0c03a01791868` | 29/29 | 74/74 | READY FOR REVIEW / unmerged |
| ADR-DX-001 PR #130 | `d7df23cac2cd1d99a668253b1b49371ab05546db` | 28/28 | not separately inspected | DRAFT / unmerged |
| AUD-FIX-06 PR #131 | `359adc3e10b2e6c700d44d97a62e046cf5b67cec` | 29/29 | not separately inspected | DRAFT / unmerged |
| AUD-FIX-05 PR #132 | `47e1128e675f035da3b907539fae3fdf0edbeb73` | 29/29 | not separately inspected | DRAFT / unmerged |
| AUD-FIX-07 PR #133 | `d0af386bc722ad2caba12e4f0f29473764a777b5` | 28/28 | not separately inspected | DRAFT / unmerged |

**Source:** live GitHub commit workflow-run collection for each exact
commit at the snapshot date; S0 check-runs collection shows 74 of 74
successful with no pending or failed checks. All five PRs were open and
unmerged on inspection. No one PR's success implies that their combined
changes have been built and tested together.

The S0 qualification progress document from an earlier revision describes
pending workflows and draft state. Preserve it as historical provenance;
do not silently rewrite it to describe later outcomes.

## 2. Historical v1.2.0 identity and registry evidence

| Evidence type | Observed GitHub value | Verification level |
|---|---|---|
| Annotated Git tag | `v1.2.0`, tag object `587d6b806d098b951916b7ad219b08d62ff7ca5c` | GitHub ref metadata checked |
| Tagged source commit | `e0ae1c67ccc488918dbef845b799caf7aba3ab70` | From S0 release provenance; tag-object dereference still requires recheck |
| GitHub Release | `v1.2.0`, published `2026-10-31T05:45:21Z`, not draft, not prerelease | GitHub Release metadata checked |
| wheel `pycrmkit-1.2.0-py3-none-any.whl` | SHA256 `83584d2566b1578558e0c04af564a8e3969f128c5d9db41e96d686f6d3a64350` | GitHub API asset digest only |
| sdist `pycrmkit-1.2.0.tar.gz` | SHA256 `01c0b282ca665a99c247c327513831db67aba2c3506248e9997e37dbcf608c9c` | GitHub API asset digest only |
| Release manifest | SHA256 `802e14aaecedea9e0861a4523721946e0b4d471db8d5015bd22f859cf731dcb5` | GitHub API asset digest only |
| SHA256SUMS file | SHA256 `1822a3dc3a28ddd414a1628f184d25857e1993d7b1f8d9f70379e4ee53001948` | GitHub API asset digest only |
| PyPI `pycrmkit==1.2.0` | Reported by open PR #115; not independently checked in this ledger | UNVERIFIED |

**Limitations:** Hashes are API-reported metadata, not a byte-level
independent download and rehash; PyPI metadata and published artifact
hashes must be verified from the live PyPI registry. No direct
snapshot-time proof of installed sdist->wheel equivalence is recorded here.

## 3. Required gate decisions, owners and evidence

| Gate | Condition | Responsible reviewer | State |
|---|---|---|---|
| S0 | Independent GitHub bytes + PyPI release proof; PR #115 decision; security and exact main merge SHA validation | Maintainer + independent security / release reviewer | NO-GO |
| S1 | AUD-FIX-05..08 reviewed and merged into qualified integration; truthful docs/skills, installed wheel tests, actor/KPI/CLI boundaries | Maintainer + domain/API + security reviewer | NO-GO |
| RC | Privacy/data purpose, minimization, rights, retention, agent governance; final compatibility matrix and evidence freeze | Maintainer + privacy/security + release reviewer | NO-GO |
| Stable v1.3.0 | Go decision, exact main SHA tests, canonical version, annotated tag, GitHub/PyPI published byte equality, closeout dossier | Release owner | NOT STARTED |

## 4. Release-readiness checklist

- [ ] Reconcile historical PR #115 as merge-or-close with retained evidence.
- [ ] Independently download / hash GitHub v1.2.0 wheel and sdist.
- [ ] Independently verify PyPI v1.2.0 existence, metadata and hashes.
- [ ] Review all S0 / S1 documents and their actual merged runtime behavior.
- [ ] Inspect and reconcile test skip lists, security findings and compatibility.
- [ ] Provide data protection analysis and host privacy obligations.
- [ ] Qualify combined Track S integration on the **new exact merge SHA**.
- [ ] Record maintainer sign-off of S0, S1 and RC gates in immutable records.
- [ ] Only then perform release candidate promotion and stable release steps
      according to the versioning strategy and published artifact contracts.

## 5. Evidence handling

No existing versioned tag, release asset, manifest, SHA256SUMS or historical
test is changed by this document. Subsequent evidence must append a new
dated ledger entry referencing the exact new SHA, workflow run identifiers,
distribution hashes, validation environment and reviewer approval.

**Decision: NO-GO for S0/S1/RC/stable at this evidence snapshot.**
