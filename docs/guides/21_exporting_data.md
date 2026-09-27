# Exporting Data

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter completes **LEVEL 5 - Data Operations**.

Chapter 20 reconciled reviewed duplicate Contacts transactionally. Chapter 21
crosses the final Data Operations boundary: turning application-selected CRM
state into portable CSV, JSON or JSONL records.

The stable V1 export model is deliberately small:

~~~text
Repository / application query
        |
        v
deterministic entity selection
        |
        v
application projection
        |
        v
Mapping[str, object] records
        |
        +--> CSVExporter
        +--> JSONExporter
        +--> JSONLExporter
        |
        v
text stream or filesystem path
~~~

The critical design principle is:

> PyCRMKit V1 exporters serialize records. They do not decide which CRM data is
> safe, relevant or authorized to export.

## What you will build

You will learn to:

- understand the stable exporter surface;
- distinguish domain selection from serialization;
- project domain entities into provider-neutral mappings;
- export CSV records with explicit or inferred fields;
- export JSON arrays incrementally;
- export JSONL one record per line;
- preserve Unicode;
- understand format-specific scalar and nested-value rules;
- understand deterministic ordering requirements;
- export paginated repository results without loading every entity at once;
- understand partial-write behavior;
- design an application-level privacy boundary;
- understand what round-trip guarantees do and do not exist;
- close the complete Data Operations loop.

## 1. Export is not a repository concern

Repositories answer questions such as:

~~~text
Which Contacts match this query?
What order are they returned in?
How is pagination applied?
~~~

Exporters answer a different question:

~~~text
How should these mapping-shaped records be written?
~~~

Stable V1 keeps those responsibilities separate.

## 2. Stable public exporter surface

The public exporter package exposes:

~~~text
CSVExporter
JSONExporter
JSONLExporter
~~~

through:

~~~python
from pycrmkit.exporters import (
    CSVExporter,
    JSONExporter,
    JSONLExporter,
)
~~~

There is no generic ExportService in stable V1.

## 3. There is no crm.exports facade

Stable V1 does not expose a crm.exports service or a Contact export method.

Applications query CRM state first and then pass projected records to an
exporter.

This prevents serialization-format concerns from becoming part of the domain
facade.

## 4. Exporters consume mappings

All three exporters accept an iterable of:

~~~text
Mapping[str, object]
~~~

Conceptually:

~~~python
records = (
    {
        "entity_id": "contact-1",
        "display_name": "Ada Lovelace",
        "email": "ada@example.com",
    },
)
~~~

The exporter does not require Contact, Organization or another domain entity.

## 5. Projection is application-owned

A Contact contains typed IDs, value objects, timestamps, lifecycle state and
metadata.

An exporter does not flatten that aggregate automatically.

The application chooses the portable record shape.

## 6. Why projection remains explicit

Automatic entity serialization would have to decide:

~~~text
which fields are public?
which email is primary?
which metadata keys are allowed?
should archived Contacts appear?
should ExternalIdentity values be included?
how are Custom Fields flattened?
how are value objects represented?
~~~

Those are application policy decisions.

## 7. Minimal Contact projection

A small projection can be:

~~~python
def export_contact(contact):
    return {
        "entity_id": str(contact.id),
        "display_name": contact.display_name or "",
        "email": (
            contact.emails[0].normalized
            if contact.emails
            else ""
        ),
        "source": contact.source or "",
    }
~~~

The resulting mapping is portable and exporter-neutral.

## 8. Query before export

A normal flow is:

~~~text
ContactRepository / CRM facade
        |
        v
ContactQuery
        |
        v
Page[Contact]
        |
        v
project Contact -> mapping
        |
        v
exporter.write(...)
~~~

Exporters do not query repositories themselves.

## 9. Ordering begins upstream

All three exporters preserve the order in which records are supplied.

Therefore:

~~~text
deterministic export
requires
deterministic source ordering
~~~

Repository ordering policy remains important.

## 10. CSVExporter

Construction:

~~~python
CSVExporter(
    destination,
    fieldnames=None,
    encoding="utf-8",
    delimiter=",",
    lineterminator="\n",
)
~~~

destination may be a filesystem path or a text stream.

## 11. CSV inferred header

When fieldnames is omitted, CSVExporter consumes the first record and uses its
key order as the header.

That makes the first mapping part of the effective tabular schema.

## 12. Explicit CSV schema is safer for machine contracts

Prefer:

~~~python
CSVExporter(
    stream,
    fieldnames=(
        "entity_id",
        "display_name",
        "email",
    ),
)
~~~

when consumers depend on a stable column order.

## 13. CSV field-name validation

Configured or inferred field names must be non-empty and unique.

Errors are:

~~~text
export.csv.header.invalid
export.csv.header.duplicate
~~~

Both are ValidationError codes.

## 14. CSV delimiter validation

delimiter must contain exactly one character.

Invalid configuration raises:

~~~text
ValidationError
code = export.csv.delimiter.invalid
~~~

## 15. CSV scalar boundary

CSVExporter accepts:

~~~text
str
int
float
bool
Decimal
date
datetime
UUID
None
~~~

Nested dict, list or set values are outside the stable CSV cell contract.

## 16. Nested CSV values are rejected

A nested value raises:

~~~text
ValidationError
code = export.csv.value.invalid
~~~

The context includes the field and Python type.

## 17. CSV nested business data requires flattening

Instead of exporting:

~~~text
custom_fields = {"tier": "gold"}
~~~

project a flat field such as:

~~~text
custom_tier = "gold"
~~~

or encode the nested value yourself according to an application contract.

## 18. Unexpected CSV fields are rejected

Once a header is fixed, a record may omit configured fields but may not add keys
outside the header.

Extra keys raise:

~~~text
ValidationError
code = export.csv.fields.unexpected
~~~

The context includes row and sorted unexpected field names.

## 19. Missing CSV fields become empty cells

Configured fields are read with mapping get semantics.

A missing key therefore becomes None and is written as an empty CSV cell.

## 20. Empty CSV input

With no configured fieldnames:

~~~text
rows written = 0
no header emitted
~~~

With configured fieldnames:

~~~text
header emitted
rows written = 0
~~~

## 21. CSV return value

write returns the number of data rows emitted.

The header is not counted.

## 22. CSV values are not domain-normalized

CSVExporter validates scalar shape but does not normalize email, phone, IDs,
timestamps or money.

Projection must define those semantics before serialization when they matter.

## 23. CSV round-trip is textual

CSVReader returns source cells as strings.

Therefore a CSV export/import round-trip does not preserve arbitrary Python
scalar types.

For example:

~~~text
True -> "True"
3 -> "3"
~~~

after reading the CSV again.

## 24. JSONExporter

Construction:

~~~python
JSONExporter(
    destination,
    encoding="utf-8",
    ensure_ascii=False,
)
~~~

It writes a top-level JSON array.

## 25. JSON output is incremental by record

JSONExporter writes one encoded record at a time rather than first converting the
complete iterable to a list.

This avoids collection-level buffering of the whole dataset.

## 26. One JSON record is still encoded as one unit

The exporter copies each mapping to dict and encodes that record.

The whole dataset need not fit in memory, but each individual record still must.

## 27. JSON Unicode default

ensure_ascii defaults to false.

Unicode text is therefore emitted directly instead of being forced into ASCII
escape sequences.

## 28. JSON compact output

The encoder uses compact separators.

The stable output is intended for machine exchange rather than pretty printing.

## 29. JSON supports nested JSON-compatible values

Mappings and lists are supported when their contained values are compatible with
the standard JSON encoder.

That makes JSON suitable for nested tags, simple custom-field mappings and other
explicitly projected structures.

## 30. JSON does not serialize domain-specific Python values automatically

Stable V1 JSONExporter does not provide a custom default serializer.

Values such as these must be projected first:

~~~text
Decimal
UUID
date
datetime
domain entities
value objects
set
~~~

## 31. JSON invalid values

A non-serializable record raises:

~~~text
ValidationError
code = export.json.value.invalid
~~~

The context includes the one-based row number.

## 32. JSON key order

JSONExporter copies each input mapping with normal Python dict semantics and does
not sort keys.

If key order matters, construct the projected mapping deterministically.

## 33. Empty JSON input

An empty iterable produces an empty JSON array followed by a newline.

The returned count is zero.

## 34. JSONLExporter

JSONL writes one complete JSON object per line:

~~~text
{"entity_id":"contact-1","name":"Ada"}
{"entity_id":"contact-2","name":"Grace"}
~~~

There is no enclosing array.

## 35. JSONL is naturally stream-oriented

Each record is written as one line before the next record is consumed.

This is useful for large sequential exports, pipes and line-oriented ingestion.

## 36. JSONL value compatibility

JSONL uses the same standard JSON encoding boundary as JSONExporter.

Nested JSON-compatible values are allowed. Domain-specific Python values must be
projected first.

## 37. JSONL invalid values

A non-serializable record raises:

~~~text
ValidationError
code = export.jsonl.value.invalid
~~~

with the one-based row number in context.

## 38. Empty JSONL input

An empty iterable writes no lines and returns zero.

## 39. Duplicate records are preserved

Exporters never deduplicate records.

If the input iterable yields the same mapping twice, two records are written.

Deduplication belongs before export if an application requires it.

## 40. All exporters preserve source row order

No exporter sorts rows.

The query or generator layer owns ordering semantics.

## 41. Determinism has two levels

Record determinism:

~~~text
same record sequence
-> same emitted row sequence
~~~

Schema determinism:

~~~text
CSV
-> explicit fieldnames preferred

JSON / JSONL
-> deterministic projected key insertion order
~~~

## 42. Repository pagination is still required for large datasets

Do not materialize every Contact simply because the exporter accepts an iterable.

Use a generator that retrieves bounded pages.

## 43. Paginated export pattern

Conceptually:

~~~python
def iter_contacts(crm, page_size=500):
    offset = 0

    while True:
        page = crm.contacts.search(
            ContactQuery(),
            OffsetPageRequest(
                limit=page_size,
                offset=offset,
            ),
        )

        for contact in page.items:
            yield export_contact(contact)

        if not page.has_next:
            break

        offset += page_size
~~~

Then:

~~~python
JSONLExporter(stream).write(
    iter_contacts(crm)
)
~~~

The exporter remains unaware of repository mechanics.

## 44. Stable ordering must accompany pagination

Offset pagination relies on deterministic repository ordering under a stable
dataset.

Export code must not depend on unordered backend results.

## 45. Streaming is not snapshot isolation

Fetching pages over time controls memory behavior. It does not create a database
snapshot.

If concurrent writes matter, the application may need a snapshot transaction,
cutoff timestamp or another consistency strategy.

Stable V1 exporters do not create that boundary.

## 46. Exporters do not open a Unit of Work

They do not start transactions, commit, roll back, lock rows or capture a
database snapshot.

They only serialize the records supplied to them.

## 47. Exporters are not atomic artifact writers

Records are emitted progressively.

If a later record fails validation or serialization, earlier output may already
exist.

## 48. JSON partial-write behavior

If JSONExporter fails after previous rows have been written, the destination may
contain an incomplete JSON array.

The exporter does not rewind or delete it.

## 49. JSONL partial-write behavior

If JSONLExporter fails on row N, rows before N have already been written as
complete lines.

Application policy decides whether that prefix is usable.

## 50. CSV partial-write behavior

CSVExporter can already have written the header and previous rows when a later
record fails.

There is no exporter-level rollback.

## 51. Atomic artifact publication belongs above the exporter

When all-or-nothing publication is required, an application can:

~~~text
write temporary artifact
        |
        v
complete and validate
        |
        v
publish / rename atomically
~~~

That orchestration is outside the format adapters.

## 52. Destination ownership

For a filesystem path, the exporter opens and closes the file.

For an existing text stream, the caller owns the stream lifecycle.

## 53. Existing path contents are replaced

Path destinations are opened in write mode.

Applications that require versioned artifacts should choose versioned paths or an
external object-storage publication strategy.

## 54. Export and privacy

CRM exports can contain personal or commercially sensitive data.

Exporters do not automatically redact email, phone, address, external IDs,
metadata or custom fields.

They write the projected record they receive.

## 55. Projection is the primary privacy boundary

A safer model is:

~~~text
Domain entity
    |
    v
authorized projection
    |
    +--> include
    +--> omit
    +--> mask
    +--> transform
    |
    v
export record
    |
    v
writer
~~~

Do not rely on a file-format adapter to enforce business authorization.

## 56. Avoid exporting metadata wholesale by default

Metadata can contain integration or operational context.

Prefer selected documented fields unless the exchange contract explicitly
requires the full mapping.

## 57. ExternalIdentity export is explicit

Stable exporters do not look up ExternalIdentity records.

If an export needs them, the application must query, authorize and project the
required provider key representation.

## 58. Custom Field export is explicit

Exporters do not discover definitions, flatten keys, resolve schema versions or
apply visibility policy.

Projection code chooses the representation.

## 59. Archived Contact inclusion is explicit

Exporters know nothing about ContactStatus.

Whether archived records are included depends entirely on upstream query policy.

## 60. Export is read-oriented and emits no DomainEvent

CSVExporter, JSONExporter and JSONLExporter do not publish export events.

An application that needs an export-completed event must define and orchestrate
that contract separately.

## 61. Exporters append no AuditEntry

No AuditService is invoked by the stable format writers.

Applications that must audit export access should record a deliberately
privacy-minimized audit entry in their orchestration layer.

## 62. Provider-neutral record design

Prefer domain-facing portable names rather than persistence internals.

For example:

~~~text
entity_id
display_name
email
source
status
external_system
external_id
~~~

when those fields belong to the intended exchange contract.

## 63. Import and export are intentionally asymmetric

Import performs:

~~~text
Read
Map
Normalize
Validate
Deduplicate
Persist
Report
~~~

Stable V1 export performs:

~~~text
application query
application projection
format serialization
~~~

There is no reverse ImportPipeline object.

## 64. Round-trip guarantees are format-specific

CSV can round-trip textual scalar records while preserving row order and
duplicates, but source values are read back as strings.

JSON and JSONL can round-trip JSON-compatible nested mappings and lists.

None of these operations automatically reconstructs CRM entities.

## 65. Complete CSV example

~~~python
from io import StringIO

from pycrmkit.exporters import CSVExporter

output = StringIO()

count = CSVExporter(
    output,
    fieldnames=(
        "entity_id",
        "display_name",
        "email",
    ),
).write(
    (
        {
            "entity_id": "contact-1",
            "display_name": "Ada Lovelace",
            "email": "ada@example.com",
        },
        {
            "entity_id": "contact-2",
            "display_name": "Grace Hopper",
            "email": "grace@example.com",
        },
    )
)

assert count == 2
~~~

## 66. Complete JSON example

~~~python
output = StringIO()

count = JSONExporter(output).write(
    (
        {
            "entity_id": "contact-1",
            "display_name": "Ada Lovelace",
            "tags": ["vip", "research"],
            "custom_fields": {
                "tier": "gold",
            },
        },
    )
)

assert count == 1
~~~

## 67. Complete JSONL generator example

~~~python
def records():
    for index in range(10_000):
        yield {
            "entity_id": f"contact-{index}",
            "display_name": f"Contact {index}",
        }

count = JSONLExporter(output).write(records())

assert count == 10_000
~~~

The exporter consumes the iterable progressively.

## 68. Project typed IDs explicitly

For portable text or JSON contracts:

~~~python
{
    "entity_id": str(contact.id),
}
~~~

JSONExporter does not serialize PyCRMKit typed IDs automatically.

## 69. Project datetime explicitly

For JSON or JSONL:

~~~python
{
    "created_at": contact.created_at.isoformat(),
}
~~~

This makes the wire contract visible.

## 70. Project Decimal explicitly

Choose the application's public representation first:

~~~text
decimal string
integer minor units
structured amount + currency
other documented representation
~~~

JSONExporter itself does not choose.

## 71. Project enum or status values explicitly

Prefer stable public values:

~~~python
{
    "status": contact.status.value,
}
~~~

rather than passing enum objects to standard JSON encoding.

## 72. Export error codes

Stable V1 format errors include:

~~~text
export.csv.header.invalid
export.csv.header.duplicate
export.csv.delimiter.invalid
export.csv.value.invalid
export.csv.fields.unexpected

export.json.value.invalid

export.jsonl.value.invalid
~~~

Applications may map these typed ValidationError codes at their own boundary.

## 73. Data Operations end-to-end flow

LEVEL 5 now forms a complete exchange and reconciliation loop:

~~~text
External Identity
      |
      v
Import
      |
      v
Normalize / Validate
      |
      v
Deduplicate
      |
      v
Review evidence
      |
      v
Merge
      |
      v
Archive duplicate
      |
      v
Query canonical state
      |
      v
Project authorized records
      |
      v
Export CSV / JSON / JSONL
~~~

## 74. Export sees post-merge canonical state only if the query chooses it

Merge archives the duplicate Contact.

An application exporting only active Contacts can emit the survivor without the
archived duplicate.

That behavior comes from query policy, not exporter filtering.

## 75. ExternalIdentity remains on the survivor after merge

Chapter 20 moved ExternalIdentity ownership to the primary Contact.

A post-merge export may project that identity from the survivor when the
application explicitly includes it.

## 76. Audit provenance and export data are separate concerns

Merge AuditEntry records preserve minimized operational evidence.

Exporters do not automatically include Audit history or DedupProvenance.

Those require explicit secured query and projection.

## Common mistakes

### Looking for crm.exports

Stable V1 exposes format writers directly, not an export facade.

### Passing Contact objects directly to JSONExporter

Project them to mapping-shaped JSON-compatible records first.

### Expecting JSONExporter to serialize Decimal or datetime automatically

It uses the standard JSON encoder without a domain-specific default serializer.

### Passing nested mappings to CSVExporter

CSV is scalar and tabular in stable V1.

### Inferring CSV fields from an unstable first record

Use explicit fieldnames for durable machine contracts.

### Assuming exporters sort records

They preserve source order. Deterministic ordering starts upstream.

### Loading the complete CRM before export

Iterate paginated repository results and yield projected records.

### Assuming streaming provides snapshot consistency

Streaming controls collection memory, not database consistency.

### Assuming a failed export rolls back written bytes

Exporters are progressive writers, not transactional artifact stores.

### Exporting metadata wholesale

Projection is the privacy boundary. Select fields deliberately.

### Assuming ExternalIdentity or Custom Fields are exported automatically

They require explicit lookup and projection.

### Treating CSV round-trip as type-preserving

CSVReader returns textual cells.

### Expecting an export DomainEvent or AuditEntry

Stable V1 exporters create neither.

## Testing Exporting Data

Projection tests should cover:

~~~text
Contact -> mapping
typed ID -> string
datetime -> explicit representation
status -> stable value
primary contact-point selection
privacy field omission
custom-field inclusion policy
external-identity inclusion policy
~~~

CSV tests should cover:

~~~text
explicit field order
inferred field order
empty input
header-only empty export
missing fields
unexpected fields
duplicate headers
invalid delimiter
nested-value rejection
Unicode
round-trip textual values
~~~

JSON tests should cover:

~~~text
empty array
Unicode
nested mappings/lists
duplicate records
source order
non-serializable values
path and stream destinations
~~~

JSONL tests should cover:

~~~text
empty input
one-object-per-line
Unicode
duplicate records
generator input
large sequential batch
non-serializable values
path and stream destinations
~~~

Application integration tests should cover:

~~~text
repository pagination
deterministic ordering
active/archive policy
post-merge survivor export
privacy projection
partial-write policy where required
~~~

## What you learned

You can now explain and use:

- CSVExporter;
- JSONExporter;
- JSONLExporter;
- mapping-shaped export records;
- application-owned projection;
- explicit CSV field schemas;
- CSV scalar boundaries;
- JSON and JSONL compatibility boundaries;
- Unicode behavior;
- source-order preservation;
- deterministic upstream ordering;
- paginated export iterators;
- bounded collection memory;
- the distinction between streaming and snapshot consistency;
- partial-write semantics;
- application-owned atomic artifact publication;
- explicit Custom Field and ExternalIdentity projection;
- explicit privacy and authorization boundaries;
- format-specific round-trip semantics;
- export ValidationError codes;
- the distinction between export, Audit and Domain Events.

## LEVEL 5 complete

The complete Data Operations learning path is now:

~~~text
17 External Identities
18 Importing Data
19 Deduplication
20 Contact Merge
21 Exporting Data
~~~

PyCRMKit V1 can now support the complete application flow:

~~~text
identify external records
        |
        v
ingest portable records
        |
        v
normalize and validate
        |
        v
detect duplicate evidence
        |
        v
merge reviewed duplicates
        |
        v
export canonical authorized records
~~~

The level closes without coupling format writers to repositories, domain facades
or privacy decisions.

## Next

The next chapter is **22 - Memory Adapter**.

LEVEL 6 begins below the domain/application layer:

~~~text
Domain services
      |
      v
Repository contracts
      |
      v
Memory Adapter
      |
      v
Unit of Work
~~~

The next learning question is:

> How does the Memory Adapter implement PyCRMKit repository and transaction
> contracts closely enough to behave like a real supported persistence backend
> rather than a permissive mock?
