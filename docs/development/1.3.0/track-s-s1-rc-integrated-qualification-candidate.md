# Track S - S1 + RC Integrated Qualification Candidate

**Date:** 2026-10-31
**Version target:** PyCRMKit 1.3.0 development (NO RELEASE)
**Status:** INTEGRATION CANDIDATE / NO-GO for merge to main and publication
**Base:** S0 PR #129 at `600fddbc29eb2fc0a1ab290e2ea0c03a01791868`
**Branch:** `integration/track-s-s1-rc-qualification`

## 1. Input provenance and exact source SHAs

This integration candidate combines the file contents from five PR HEADs
against the common S0 base. All changes were checked to be nonoverlapping
(53 unique changed files). Content blob SHA is copied from the GitHub
compare API for each source, not reconstructed from a textual patch.

| Scope | Source PR | Exact source SHA | Files |
|---|---|---|---:|
| AUD-FIX-08 | #130 | `d7df23cac2cd1d99a668253b1b49371ab05546db` | 1 |
| AUD-FIX-06 | #131 | `359adc3e10b2e6c700d44d97a62e046cf5b67cec` | 18 |
| AUD-FIX-05 | #132 | `47e1128e675f035da3b907539fae3fdf0edbeb73` | 11 |
| AUD-FIX-07 | #133 | `d0af386bc722ad2caba12e4f0f29473764a777b5` | 6 |
| AUD-FIX-09 | #134 | `6fd3ac2ab56c90162c2aa2950cfb05e396530402` | 17 |

The PRs remain open; integration here does NOT merge their Git commit
histories, constitute an approved code review or close audit issues.
The S0 integration branch and `main` are unmodified by this candidate.

## 2. What must be qualified on this NEW integrated SHA

- All Ruff, mypy, tests for Python 3.11, 3.12 and 3.13, packaging,
  wheel/sdist installation, Django/SQLAlchemy/PostgreSQL 17 and optional
  FastAPI/DRF integrations, migration, security and compatibility workflows.
- Complete CLI feature tours from the installed wheel (PR #131).
- Documentation to CLI/agent contract alignment (PR #132).
- Claimed actor propagation, mocked provider disclosure, and observed-only
  multi-currency, stage and pagination semantics (PR #133).
- Privacy safeguards in all seven domain blueprints and seven agent recipes,
  and an evidence ledger preserving v1.2.0 provenance (PR #134).
- Domain/API boundary and future Customer 360 ownership from ADR-DX-001
  (PR #130), which is still PROPOSED and not formally ACCEPTED.
- Review any deviations in `workflow.md` files and uncategorized code
  samples. A passing classification test does not prove every snippet works.
- Large-dataset pagination and cross-adapter consistency tests still must
  be reviewed; the dashboard continues to display an explicitly partial
  sample, not a complete Customer 360 projection.

## 3. Trust and dependency gates

| Gate | Requirement | Decision |
|---|---|---|
| S0 | Human review and acceptance of PR #129; independent historical 1.2.0 GitHub/PyPI artifact hashes; decision on PR #115; post-merge qualification on main merge SHA | NO-GO |
| S1 | Final HEAD tests and review of PR #130..133; explicit closure of AUD-FIX-05..08 acceptance conditions; feature-tour, installed artifact, actor, KPI and architecture contracts | NO-GO |
| RC | PR #134 privacy/security/governance review, subject-rights/retention host responsibilities, release evidence correctness and documentation truth | NO-GO |
| v1.3.0 | Final integrated source and new versioned RC SHA qualified, maintainer release approval, artifact identity and distribution chain | NOT STARTED |

## 4. CI and evidence policy

A successful check on any individual PR SHA is not proof of compatibility
after integration. This candidate requires a **new exact SHA** check matrix.
Record GitHub check run count and workflow outcomes, any skip/migration
deviations and the exact reviewed artifact hashes in a separate dated
append-only qualification note.

Do not rewrite historic `v1.2.0` test evidence, tag, release archive,
GitHub Release or published PyPI distribution. Treat data obtained from
GitHub release APIs as API metadata until asset bytes are independently
downloaded and verified.

## 5. Intended next actions

1. Review all failures of this integrated PR, repair only this branch (or
   bring corrections back to their source PR with provenance).
2. Review and obtain explicit governance approvals for the three gates.
3. After S0 authorized merge and post-merge check, rebase or reconstruct
   the S1/RC candidate on the new `main` SHA.
4. Accept/close the individual AUD-FIX issues only when their full DoD
   is met. No release, tag or PyPI promotion before final authorization.
