# Campaign Data Operations - 1.2.0b3 (beta candidate)

Campaign DataOps adds **Python API** entrypoints for importing direct Campaign members and exporting three separate views. There is no HTTP file-upload endpoint. Import and export must be authorized by your application's caller policy **before** invoking these Python functions. The HTTP Campaign policy is not automatically applied to direct Python calls.

## Runnable example

```bash
python examples/data_operations/campaign_scenario.py
```

The example creates two Contacts, a Campaign and one captured Segment source, imports two direct members from CSV, replays those rows, then exports the audience and provenance. It runs without optional web or ORM dependencies and is tested from a clean wheel and sdist installation.

## Import direct members

```python
from pathlib import Path
from pycrmkit.campaigns import import_campaign_members
from pycrmkit.importers import CSVReader

# crm and campaign_id come from your trusted application context.
report = import_campaign_members(
    crm.campaigns,
    campaign_id,
    CSVReader(Path("direct-members.csv")),
    source="consented-crm-upload",
    max_rows=1000,
)

print(report.as_dict())
for error in report.errors:
    print(error.row_number, error.code, error.stage)
```

The CSV has **two required fields**:

```csv
entity_kind,entity_id
contact,00000000-0000-4000-8000-000000000011
organization,00000000-0000-4000-8000-000000000012
```

The entity types are `contact`, `organization`, `lead` and `opportunity`. Each UUID must refer to an existing target entity in the CRM. Use `JSONReader` for an array of objects, or `JSONLReader` for one object per line. A `RecordMapper` can convert source column names to `entity_kind` and `entity_id`.

The row limit is validated and the file is pre-read up to the configured maximum plus one; oversize/malformed files fail **before** any writes. Other valid rows can commit before later row-level validation failures. Only the specific `campaign.member.not_found` domain error is recovered into a row report. Database errors, unexpected domain errors and concurrent unique conflicts abort the current invocation and can leave earlier rows committed. **No batch atomicity, durable idempotency keys, distributed exactly-once, or automatic rollback are promised.**

On a replay, existing direct members are skipped. A Contact present only in a captured Segment is still eligible for direct insertion without changing the captured membership or the deduplicated final audience count.

## Export direct, audience and source provenance

```python
from pathlib import Path
from pycrmkit.campaigns import export_campaign_records

exported = export_campaign_records(
    crm.campaigns,
    campaign_id,
    Path("audience.jsonl"),
    kind="audience",
    format="jsonl",
    page_size=100,
)
print(exported)
```

| Kind | Purpose | Fields |
|---|---|---|
| `direct` | Explicitly added members, with their own provenance | campaign_id, entity_kind, entity_id, source, added_at |
| `audience` | Deduplicated union of direct and captured Segment entities | campaign_id, entity_kind, entity_id |
| `sources` | Materialized Segment provenance, **not** individual recipient details | campaign_id, segment_id, segment_revision, entity_kind, attached_at, captured_at, member_count |

Choose `format="csv"`, `"json"` or `"jsonl"`. All variants use the existing exporter implementations. Page sizes range from 1 to 200, default 50; offset pagination is **not a consistent snapshot** during concurrent writes. For reproducible full-population exports, stop source mutations or use application-owned transaction/snapshot facilities.

All exported identifiers are customer data in context, even when the file has no names or email addresses. Enforce the application's export authorization, retention policy, storage permissions, logging redaction, and safe CSV consumption. No full CommunicationRecord body, recipient content or actor ID is exported automatically.

## Contract and qualification

- Source code: `pycrmkit.campaigns.data_operations`; re-exported under `pycrmkit.campaigns`.
- Source/wheel/sdist smoke: `examples/data_operations/campaign_scenario.py`.
- Integration suites: `tests/integrations/test_campaign_dataops_import.py` and `test_campaign_dataops_export.py`.
- PostgreSQL SQLAlchemy: `tests/e2e/test_campaign_sqlalchemy_end_to_end.py`.
- Django persistence: `tests/integrations/django/test_campaign_persistence.py`.
- Workflows: `.github/workflows/data-operations-e2e.yml`, `postgresql.yml`, `django-e2e.yml`.

The standard `ImportPipeline` API was **not** extended: it remains frozen for existing V1 consumers. Campaign uses a dedicated report-producing runner.
