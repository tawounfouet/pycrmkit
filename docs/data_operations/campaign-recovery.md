# PyCRMKit Campaign - Import Recovery and Replay Playbook

**Qualified scope:** LOT-31-007 - Import Replay & Failure Qualification  
**Candidate source:** v1.2.0b3 workstream for 1.2.0rc1  
**Date:** 2026-10-29  
**Status:** Implementation and CI gate committed; exact SHA acceptance depends on full PR green checks. No public RC published.

## 1. The reliability contract

`import_campaign_members(campaigns, campaign_id, reader, ...)` imports **direct Campaign memberships only**. It does not import Segment captures, modify captured Segment snapshots or turn the deduplicated union of an audience into explicit membership.

- Readers: `CSVReader`, `JSONReader`, `JSONLReader` (or an `IterableReader`). A `RecordMapper` translates input column names to `entity_kind` and `entity_id`.
- Supported kinds: `contact`, `organization`, `lead`, `opportunity`. Each `entity_id` is a UUID identifying an existing CRM entity.
- Row count limit: 1 to **1000**, with a bounded pre-read of `max_rows + 1`; an over-limit file is rejected before membership writes.
- Syntax/structural reader failures encountered during the pre-read are fatal **before writes**, even if earlier source rows were syntactically valid.
- Mapping `ValidationError` and field/member-existence validation are row-local errors. A row report is returned for a normally completed invocation, not for a fatal exception.
- Successful rows are committed **one at a time**; on repository, unexpected domain or concurrent uniqueness failure, the exception propagates and **previously committed rows remain**. The in-flight row is not claimed as persisted.
- Deduplication checks existing **direct members**, including members added earlier in the same invocation. A captured Segment member alone is *not* a direct duplicate.

This is a replay-safe **business uniqueness** pattern; it is **not** whole-file atomicity, exactly-once, a durable idempotency token, a distributed transaction, or an automatic retry protocol.

## 2. Operator recovery workflow after an interrupted import

1. **Stop retry loops.** Capture the original input as an immutable artifact, with an application-owned content hash, authorized storage location, tenant/campaign identity, row count and a separate run identifier. Avoid copying raw person identifiers into ticket titles or ordinary logs.
2. **Classify the failure.** `campaign.import.row_limit`, CSV/JSON/JSONL syntax/structural errors and preflight archive authorization fail before writes; fix the file or authorized campaign state before retry. `campaign.member.not_found` is a row-local validation error; missing CRM entities should be created or removed from the import source only with approval. Unexpected `RepositoryError`, `DuplicateError` or other exceptions may have left a partial import.
3. **Inspect committed state**, not just the failed job log. Query `crm.campaigns.members(campaign_id)` over its pages, or export `kind="direct"` through an approved and access-controlled channel. Do not infer committed row counts from an exception when no `ImportReport` was returned.
4. **Verify scope and authorization** before every Python import call. `PYCRMKIT_CAMPAIGN_SECURITY` / `CampaignHTTPAccess` protect the opt-in HTTP surface, **not** Python DataOps invocations. Enforce trusted Campaign ID, caller tenant, file provenance, operation permission and storage isolation in the host.
5. **Replay the *original corrected* complete source file**, using a fresh reader/stream and the same trusted campaign scope. Existing direct memberships become duplicates; missing direct memberships can be created. On a competing insert race, the existing function may raise `DuplicateError`; inspect committed state and retry only after resolving concurrency. Do not swallow or relabel it as success.
6. **Reconcile outcomes** with `ImportReport.as_dict()`, `row_results` / `errors` (when `retain_row_results=True`) and the paginated committed direct-member list. Validate that `rows_read = rows_created + rows_updated + rows_skipped` on a *completed* run. The count `validation_errors` counts **issues**, not necessarily distinct skipped rows. For a replay, `duplicates` is an observed skip count, not created records.
7. **Check source preservation.** Confirm captured Segment source metadata, snapshots and audience union are unchanged except the intended direct-membership additions. Do not use total audience count alone as evidence of direct membership.
8. **Record an auditable resolution** (sanitized run ID, bounded report counters, exception class/code, reconciled direct member count, actor authorization, approved retry action). Restrict export files and delete temporary originals under host retention policy.

### Minimal replay example

```python
from pathlib import Path

from pycrmkit.campaigns import import_campaign_members
from pycrmkit.importers import CSVReader

# The host must verify caller/tenant, choose the correct CRM facade and
# authorize the existing campaign_id before the call.
source = Path("validated-campaign-members.csv")
report = import_campaign_members(
    crm.campaigns,
    campaign_id,
    CSVReader(source),   # construct a new reader for every replay
    source="approved-crm-replay",
    max_rows=1000,
    retain_row_results=True,
)
print(report.as_dict())  # retain only safe counters in ordinary logs
# Review report.errors in a restricted troubleshooting channel if needed.
```

A replay can yield `rows_created=0` and `duplicates=N` even after a partially successful prior attempt. This is normal and is **not** proof that every prior attempt completed successfully.

## 3. Scenario matrix and expected observable outcomes

| Scenario | Outcome | Committed effect |
|---|---|---|
| Same corpus in CSV/JSON/JSONL | Same structured 4-row report and replay counters | 2 unique direct members; zero replay inserts |
| Mapping `kind`/`uuid` into canonical field names | Successful import on each reader | One direct member |
| Mapper rejects an individual row with a ValidationError | `ImportStage.MAP` with original row index | Earlier successful rows remain |
| 1000 input rows, repeated direct identities | Accepted; 2 creates and 998 duplicate skips | Exactly 2 new direct members |
| 1001 input rows with max_rows=1000 | `campaign.import.row_limit` | Zero writes to target Campaign |
| Trailing invalid JSON/JSONL or extra CSV columns | Reader-specific `import.*` error during pre-read | Zero writes, no member events |
| Valid UUID but missing CRM entity | `campaign.member.not_found` per-row issue | Other valid rows can still commit |
| Storage outage on second persistence call | `RepositoryError` propagates, no completed report | First member persists, subsequent rows not attempted |
| Replay after outage | First direct member skipped; remaining rows created | No logical duplicates |
| Concurrent unique conflict injection | `DuplicateError` propagates | Do not fabricate a successful insert; reconcile |
| Import of captured Segment member | Direct insert permitted, next replay duplicate | Segment source unchanged; union audience deduplicated |

## 4. Code and CI evidence

- `tests/qualification/test_campaign_import_rc.py` - canonical corpus, mapping, max rows, late parse failures, failure replay, conflict and snapshot preservation.
- `tests/integrations/test_campaign_dataops_import.py` - existing integration coverage, run alongside the new qualification suite.
- `.github/workflows/public-api-freeze.yml` - dedicated `Campaign RC1 Import Replay and Failure Qualification` step.
- `docs/data_operations/campaigns.md` - public b3 behavior and data-operations API examples.

Reproduce:

```bash
python -m pip install -e '.[dev]'
python -m pytest tests/qualification/test_campaign_import_rc.py tests/integrations/test_campaign_dataops_import.py -q
ruff check tests/qualification/test_campaign_import_rc.py
```

## 5. Acceptance and next gate

- [x] Tests and operator replay playbook authored and committed.
- [x] Cross-format report semantics, limits, known failures, partial commit replay and direct-only membership covered.
- [x] Full CI workflow integration committed.
- [ ] Exact new commit must pass 100% GitHub checks and workflows before LOT-31-007 is **QUALIFIED**.
- [ ] Live PostgreSQL two-writer uniqueness and transaction failure tests (LOT-31-009).
- [ ] Export concurrency/privacy qualification (LOT-31-008).

**Publication:** NO-GO for 1.2.0rc1 until all future release gates are satisfied. Remain on draft PR #112; do not merge or tag on this lot alone.
