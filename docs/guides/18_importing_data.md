# Importing Data

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 5 - Data Operations**.

Chapter 17 established deterministic mapping from an external record to a CRM
entity. Chapter 18 scales that idea from one mapping to an import pipeline.

The stable V1 mental model is:

~~~text
Read
  |
  v
Map
  |
  v
Normalize
  |
  v
Validate
  |
  v
Deduplicate
  |
  v
Persist
  |
  v
Report
~~~

The Import Framework is provider-neutral orchestration. It does not itself
decide how to create a Contact, when to update one, or how to attach an
ExternalIdentity. Those policies belong to application-owned adapters.

## What you will build

You will learn to:

- read mapping-shaped records through ImportReader;
- use IterableReader, CSVReader, JSONReader and JSONLReader;
- translate provider fields with FieldMapping and RecordMapper;
- compose normalization rules;
- validate rows with structured issues;
- use the duplicate-detection hook;
- implement ImportPersister;
- distinguish created, updated and skipped outcomes;
- interpret ImportReport counters and row evidence;
- use retain_row_results=False for reduced report retention;
- understand which failures are reported per row and which propagate;
- integrate Contact and ExternalIdentity persistence explicitly;
- understand streaming, transaction and memory boundaries.

## 1. Import Framework is not a Contact importer

The generic pipeline knows nothing about:

~~~text
Contact
Organization
Lead
Opportunity
provider SDKs
Django
SQLAlchemy
FastAPI
~~~

It knows only import contracts.

The application decides what persistence means.

## 2. Stable public import contracts

The V1 package exports:

~~~text
ImportRow

ImportReader
ImportMapper
ImportNormalizer
ImportValidator
ImportDeduplicator
ImportPersister

IterableReader
CSVReader
JSONReader
JSONLReader

FieldMapping
RecordMapper

NormalizationRule
RecordNormalizer
strip_text
casefold_text
empty_text_to_none
compose_normalizers

RequiredFieldsValidator
PredicateValidator
CompositeValidator

DuplicateResult

PersistAction
PersistResult

ImportPipeline

ImportReport
ImportRowResult
ImportRowError
ImportRowStatus
ImportStage
~~~

Stable V1 has no crm.imports facade namespace.

## 3. ImportRow

Every yielded source record becomes:

~~~text
ImportRow
├── number
└── values
~~~

number starts at 1.

A number below 1 raises:

~~~text
ValidationError
code = import.row.number.invalid
~~~

## 4. ImportRow values are top-level immutable

The constructor copies values and wraps the mapping in MappingProxyType.

This prevents reassignment such as:

~~~python
row.values["email"] = "changed@example.com"
~~~

The top-level mapping is protected.

Nested JSON values are not recursively frozen, so a nested list or dict may
still be mutable.

## 5. ImportRow.replace

Pipeline transformations create a new row:

~~~python
new_row = row.replace(
    {
        "email": "ada@example.com",
    }
)
~~~

The logical row number remains unchanged.

## 6. ImportReader

The reader contract is:

~~~python
def read(
    self,
) -> Iterable[Mapping[str, object]]:
    ...
~~~

Records are yielded in source order.

The pipeline enumerates yielded records starting at 1.

## 7. IterableReader

IterableReader adapts an existing iterable of mappings.

~~~python
reader = IterableReader(
    (
        {
            "Email": "ada@example.com",
            "Name": "Ada Lovelace",
        },
    )
)
~~~

It is useful for in-memory sources, API adapters or application-generated
records.

## 8. Physical readers preserve duplicates

CSVReader, JSONReader and JSONLReader do not deduplicate.

Identical source rows remain separate records.

Deduplication belongs to the deduplicator stage.

## 9. CSVReader

CSVReader accepts:

~~~text
str path
PathLike path
TextIO stream
~~~

Default encoding for paths:

~~~text
utf-8-sig
~~~

Default delimiter:

~~~text
,
~~~

A custom delimiter must contain exactly one character.

Invalid delimiter:

~~~text
import.csv.delimiter.invalid
~~~

## 10. CSV header rules

CSV headers must exist when data is present, be non-empty and be unique.

Errors include:

~~~text
import.csv.header.invalid
import.csv.header.duplicate
~~~

The reader does not silently rename duplicate columns.

## 11. CSV missing and extra values

A declared column with no value may yield an empty string.

A row with more columns than the header is rejected:

~~~text
import.csv.columns.extra
~~~

The error context identifies the physical source line.

## 12. CSV is tabular text

CSVReader does not infer integers, dates, booleans or nested objects.

Application normalization owns those conversions.

## 13. JSONReader

JSONReader expects one JSON document whose root is an array of objects.

Invalid root:

~~~text
import.json.root.invalid
~~~

Invalid row type:

~~~text
import.json.row.invalid
~~~

Malformed JSON:

~~~text
import.json.syntax.invalid
~~~

Syntax errors carry line and column context.

## 14. JSON preserves nested values

JSONReader can yield:

~~~python
{
    "email": "ada@example.com",
    "custom": {
        "segment": "research",
    },
    "tags": [
        "vip",
    ],
}
~~~

Nested JSON structures are retained.

## 15. JSONReader is not streaming

JSONReader uses the standard-library document loader.

The full JSON document is materialized before array rows are yielded.

For very large inputs, do not describe JSONReader as a streaming reader.

## 16. JSONLReader

JSONLReader reads one JSON object per non-blank physical line.

Blank lines are skipped.

Malformed line:

~~~text
import.jsonl.syntax.invalid
~~~

Non-object line:

~~~text
import.jsonl.row.invalid
~~~

Errors identify the physical line.

## 17. JSONL is stream-friendly

JSONLReader parses one line at a time.

CSVReader similarly iterates records rather than materializing the full source.

For large sources, CSV or JSONL generally fit the iterable pipeline better than
a single huge JSON array.

## 18. Logical row number vs physical line

ImportPipeline numbers records after the reader yields them.

Therefore:

~~~text
ImportRow.number
= logical yielded-record number

reader error line
= physical source line
~~~

These can differ, especially when JSONL contains blank lines.

## 19. FieldMapping

One mapping rule contains:

~~~text
source
target
default
~~~

source is required and trimmed.

target may be a field name or None.

## 20. target=None explicitly ignores a field

Example:

~~~python
FieldMapping(
    "provider_note",
    None,
)
~~~

The field is intentionally removed from mapped output.

## 21. Mapping defaults

Example:

~~~python
FieldMapping(
    "Source",
    "source",
    default="legacy_crm",
)
~~~

The default is used only when the source key is absent.

If the key exists with None or an empty string, that existing value is used.

## 22. RecordMapper default output

Default:

~~~text
preserve_unmapped = False
~~~

Only declared destination fields survive.

With preserve_unmapped=True, undeclared source fields remain.

When a field is renamed, the original source key is removed.

## 23. Duplicate mapping target

Two mappings cannot write to the same destination.

Stable error:

~~~text
import.mapping.target.duplicate
~~~

Blank source/target names raise:

~~~text
import.mapping.field.empty
~~~

## 24. RecordNormalizer

RecordNormalizer applies ordered NormalizationRule values.

Example:

~~~python
RecordNormalizer(
    (
        NormalizationRule(
            "email",
            compose_normalizers(
                strip_text,
                casefold_text,
            ),
        ),
    )
)
~~~

Rules run in declaration order.

Absent fields are skipped.

## 25. skip_none

NormalizationRule.skip_none defaults to True.

If the field value is None, the normalizer is not called.

Applications may set skip_none=False when the callable explicitly handles None.

## 26. Built-in normalization helpers

strip_text:

~~~text
requires string
trims surrounding whitespace
~~~

casefold_text:

~~~text
requires string
Unicode-aware case normalization
~~~

empty_text_to_none:

~~~text
blank string -> None
other values unchanged
~~~

compose_normalizers:

~~~text
runs callables left-to-right
~~~

## 27. Normalization failures

RecordNormalizer converts TypeError and ValueError from a normalizer into:

~~~text
ValidationError
code = import.normalization.failed
~~~

Context includes:

~~~text
row
field
~~~

Existing PyCRMKitError values are re-raised rather than blindly rewritten.

## 28. RequiredFieldsValidator

RequiredFieldsValidator treats a field as missing when its value is:

~~~text
None
or
blank string after trim
~~~

It returns a ValidationIssue:

~~~text
code = import.required.missing
field = field name
~~~

Ordinary data rejection is returned, not raised.

## 29. PredicateValidator

PredicateValidator lets applications define field-specific checks.

~~~python
PredicateValidator(
    field="email",
    predicate=looks_like_email,
    code="import.email.invalid",
    message="email must contain @",
)
~~~

allow_missing defaults to True.

## 30. CompositeValidator

CompositeValidator runs validators in declaration order and concatenates all
issues.

It does not stop at the first issue.

One invalid row can therefore produce several ValidationIssue values.

## 31. validation_errors counts issues

This is an important report rule.

If one row has two validation issues:

~~~text
rows_skipped      += 1
validation_errors += 2
~~~

validation_errors is not the number of invalid rows.

## 32. ImportDeduplicator

The hook is:

~~~python
def detect(
    self,
    row: ImportRow,
) -> DuplicateResult:
    ...
~~~

Default NoDuplicateDetector always returns no match.

Deduplication is opt-in.

## 33. DuplicateResult

DuplicateResult contains:

~~~text
is_duplicate
existing_entity_id
reason
~~~

Convenience constructors:

~~~text
DuplicateResult.no_match()
DuplicateResult.match(...)
~~~

## 34. Duplicate outcome

When is_duplicate is True:

~~~text
duplicates   += 1
rows_skipped += 1
persister is not called
~~~

With detailed reporting, duplicate_entity_id is retained.

The generic ImportRowResult does not currently retain DuplicateResult.reason.

## 35. ImportPersister

The persistence protocol is intentionally small:

~~~python
def persist(
    self,
    row: ImportRow,
) -> PersistResult:
    ...
~~~

This is where application policy becomes CRM state.

## 36. PersistAction

Stable values:

~~~text
created
updated
skipped
~~~

## 37. PersistResult

PersistResult contains:

~~~text
action
entity_id
~~~

entity_id is optional and is represented as a string at this generic boundary.

## 38. CREATED, UPDATED and SKIPPED counters

CREATED:

~~~text
rows_created += 1
~~~

UPDATED:

~~~text
rows_updated += 1
~~~

SKIPPED:

~~~text
rows_skipped += 1
~~~

PersistAction.SKIPPED does not automatically increment duplicate or validation
counters.

## 39. ImportPipeline defaults

Required constructor dependencies:

~~~text
reader
persister
~~~

Defaults:

~~~text
mapper       -> IdentityMapper
normalizer   -> IdentityNormalizer
validator    -> AcceptAllValidator
deduplicator -> NoDuplicateDetector
retain_row_results -> True
~~~

## 40. Exact execution order

For each yielded record:

~~~text
ImportRow
   |
   v
mapper.map
   |
   v
normalizer.normalize
   |
   v
validator.validate
   |
   v
deduplicator.detect
   |
   v
persister.persist
   |
   v
ImportReport
~~~

## 41. Mapping ValidationError is reported per row

A ValidationError raised by mapper.map becomes:

~~~text
status = skipped
stage  = map
~~~

The pipeline continues with the next row.

## 42. Normalization ValidationError is reported per row

A ValidationError raised by normalizer.normalize becomes:

~~~text
status = skipped
stage  = normalize
~~~

The pipeline continues.

## 43. Validator issues are reported per row

Returned ValidationIssue values become:

~~~text
status = skipped
stage  = validate
~~~

Persistence is not called for that row.

## 44. Validator exceptions are different

The stable contract expects ordinary validation rejection as returned issues.

Unexpected exceptions raised by validator.validate are not converted into a
successful-looking row result.

They propagate.

## 45. Deduplicator exceptions propagate

Failures from deduplicator.detect are not swallowed.

They may represent repository or application errors.

## 46. Persister exceptions propagate

Failures from persister.persist also propagate.

Persistence may involve transactions or external state.

The framework does not hide that failure as a skipped row.

## 47. Reader structural errors propagate

Malformed CSV, JSON or JSONL is a source-level failure.

Reader ValidationError values are raised while producing records and are not
converted into ordinary ImportRowResult entries.

## 48. Why failure handling is asymmetric

Map, normalization and validation are expected data-quality boundaries.

Deduplication and persistence can fail for reasons such as:

~~~text
transaction failure
repository failure
network failure
consistency conflict
application bug
~~~

Silently counting those as skipped rows would make the report misleading.

## 49. ImportReport counters

Stable counters:

~~~text
rows_read
rows_created
rows_updated
rows_skipped
duplicates
validation_errors
~~~

as_dict returns those six values.

## 50. ImportRowResult

Detailed result fields:

~~~text
row_number
status
entity_id
duplicate
duplicate_entity_id
errors
~~~

## 51. ImportRowStatus

Stable values:

~~~text
created
updated
skipped
~~~

## 52. ImportRowError

One error retains:

~~~text
row_number
stage
code
message
field
~~~

ImportStage values are:

~~~text
map
normalize
validate
~~~

There is no deduplicate or persist row-error stage because those failures
propagate.

## 53. report.errors

report.errors flattens errors from retained row results in result order.

It does not create new evidence.

## 54. Detailed reporting is the default

Default:

~~~text
retain_row_results = True
~~~

This preserves row-level outcomes for inspection.

## 55. Summary mode

For high-volume processing:

~~~python
ImportPipeline(
    reader=reader,
    persister=persister,
    retain_row_results=False,
)
~~~

keeps exact counters while:

~~~text
row_results = []
errors = ()
~~~

## 56. What summary mode does and does not bound

It prevents ImportReport from growing one result object per row.

It does not guarantee bounded memory for every component.

Examples:

~~~text
JSONReader still loads the whole document
a custom deduplicator may cache all candidates
a persister may buffer writes
~~~

Memory behavior is compositional.

## 57. Streaming-friendly combination

A good low-retention combination is:

~~~text
CSVReader or JSONLReader
+
streaming application logic
+
retain_row_results=False
~~~

Stable V1 performance qualification uses summary mode for a 5,000-row import
scenario.

The performance ceiling is a regression guardrail, not a production SLA.

## 58. Minimal pipeline

~~~python
class ContactPersister:
    def persist(
        self,
        row: ImportRow,
    ) -> PersistResult:
        return PersistResult(
            PersistAction.CREATED,
            entity_id=f"contact-{row.number}",
        )

pipeline = ImportPipeline(
    reader=IterableReader(
        (
            {
                "Email": " Ada@Example.COM ",
                "Name": "Ada Lovelace",
            },
        )
    ),
    mapper=RecordMapper(
        (
            FieldMapping("Email", "email"),
            FieldMapping("Name", "display_name"),
        )
    ),
    normalizer=RecordNormalizer(
        (
            NormalizationRule(
                "email",
                compose_normalizers(
                    strip_text,
                    casefold_text,
                ),
            ),
        )
    ),
    validator=RequiredFieldsValidator(
        (
            "email",
            "display_name",
        )
    ),
    persister=ContactPersister(),
)

report = pipeline.run()
~~~

## 59. Mixed-outcome report

A run with one create, one update, one duplicate and one invalid row may yield:

~~~text
rows_read          4
rows_created       1
rows_updated       1
rows_skipped       2
duplicates         1
validation_errors  1
~~~

## 60. Stable Data Operations E2E

The qualified reference scenario uses:

~~~text
CSVReader
   |
   v
RecordMapper
   |
   v
RecordNormalizer
   |
   v
RequiredFieldsValidator
   |
   v
application-owned ImportPersister
   |
   v
MemoryUnitOfWork + ContactService
~~~

The application adapter bridges import mechanics to Contact persistence.

## 61. ExternalIdentity integration is explicit

The import engine does not automatically create ExternalIdentity mappings.

An application persister may compose:

~~~text
accepted row
    |
    v
Unit of Work
    |
    +--> ContactService
    |
    +--> ExternalIdentityService
    |
    v
commit
~~~

This composition is application policy.

## 62. Same-UoW Contact and ExternalIdentity creation

When atomic row persistence is required, one persister can create both inside
one Unit of Work:

~~~python
with MemoryUnitOfWork(store) as uow:
    contact = ContactService(
        uow.contacts,
        clock=clock,
    ).create(
        display_name=display_name,
    )

    ExternalIdentityService(
        uow.external_identities,
        clock=clock,
    ).attach(
        EntityReference(
            "contact",
            contact.id,
        ),
        system=system,
        external_id=external_id,
    )

    uow.commit()
~~~

The generic ImportPipeline does not open that transaction itself.

## 63. ExternalIdentity can provide deterministic import routing

An application persister can resolve:

~~~text
(system, external_id)
~~~

before deciding whether to:

~~~text
create
update
skip
review
reject conflict
~~~

The selected policy is returned as PersistResult.

## 64. Import idempotency is application-owned

Stable ImportPipeline has no built-in import idempotency key.

A repeatable importer may use ExternalIdentity, source checksums or another
application key.

The framework does not guess one universal policy.

## 65. Transaction scope is application-owned

ImportPipeline does not wrap the full run in one Unit of Work.

A persister may choose:

~~~text
one transaction per row
one transaction per chunk
a wider application-managed transaction
external side effects
~~~

## 66. Consequence of per-row commits

If rows 1 through 10 commit and row 11 raises in persistence, the pipeline
raises at row 11.

Previously committed rows remain committed.

ImportPipeline does not retroactively roll them back.

## 67. No automatic retry

Stable V1 does not retry reader, deduplicator or persister failures
automatically.

Retrying side effects requires application-specific idempotency policy.

## 68. No built-in resume cursor

ImportReport does not persist:

~~~text
job identifier
checkpoint
source checksum
resume token
last committed offset
~~~

Resumable jobs belong to application orchestration.

## 69. No generic import events

ImportPipeline does not emit generic import.created or import.row events.

If a persister invokes CRM domain operations that emit their own events, those
normal domain event semantics still apply.

## 70. Import validation is not domain validation

The layers are:

~~~text
source structure
      |
      v
import mapping/normalization/validation
      |
      v
persister
      |
      v
CRM domain validation
~~~

Passing import validation does not guarantee ContactService or another domain
service will accept the values.

## 71. Domain errors in persistence propagate

If a domain service rejects a row during persister.persist, the exception
propagates unless the application explicitly converts it before calling the
pipeline persistence boundary.

The generic pipeline does not reinterpret arbitrary domain failures.

## 72. Validate useful source preconditions early

Import validators are useful for:

~~~text
required columns
basic syntax
known reference codes
parseable scalar values
allowed source ranges
~~~

The domain remains the final authority for aggregate invariants.

## 73. CSV example

~~~text
Email,Name,Source
 Ada@Example.COM , Ada Lovelace , Campaign
~~~

RecordMapper can rename fields, then RecordNormalizer can strip and casefold
selected values before validation.

## 74. JSON example

~~~json
[
  {
    "email": "ada@example.com",
    "custom_fields": {
      "segment": "research"
    },
    "tags": [
      "vip"
    ]
  }
]
~~~

Nested values remain available to application persistence logic.

## 75. JSONL example

~~~text
{"email":"user-1@example.com"}
{"email":"user-2@example.com"}
{"email":"user-3@example.com"}
~~~

This format is suitable for line-by-line processing.

## 76. Mapping failure evidence

A custom mapper ValidationError becomes an ImportRowError with:

~~~text
stage = map
code = mapper error code
~~~

## 77. Normalization failure evidence

Passing an integer to strip_text produces a normalized pipeline error:

~~~text
stage = normalize
code  = import.normalization.failed
field = configured field
~~~

## 78. Validation evidence

RequiredFieldsValidator can produce:

~~~text
stage = validate
code  = import.required.missing
field = email
~~~

## 79. Duplicate evidence

A deduplicator can return:

~~~python
DuplicateResult.match(
    existing_entity_id="contact-existing",
    reason="normalized email",
)
~~~

The report records the existing entity ID.

The generic row result does not retain reason.

## 80. Persisted entity IDs

PersistResult.entity_id is copied into detailed ImportRowResult.

Applications may later parse the string back to a typed ID when appropriate.

## 81. Privacy

Source rows may contain personal or sensitive data.

The built-in row error model stores:

~~~text
row number
stage
code
message
field
~~~

It does not automatically copy the full input record.

Applications should avoid embedding secrets or full personal values into custom
error messages.

## 82. External IDs and privacy

When imported data includes external identifiers, use the privacy principle from
chapter 17:

~~~text
keep identifiers in explicit data paths
avoid copying them into generic events/logs/errors unless required
~~~

## 83. Custom readers

ImportReader is structural typing.

Applications can adapt:

~~~text
database cursors
paginated APIs
object-storage streams
message batches
spreadsheet sources
~~~

without changing ImportPipeline.

## 84. Custom normalizers

Applications can normalize:

~~~text
dates
decimals
country codes
enums
booleans
provider-specific values
~~~

For expected bad source data, use a ValidationError that the pipeline can report
at the normalization stage.

## 85. Custom validators

Validators can consult application configuration or reference data.

Ordinary rejected rows should return ValidationIssue values.

Infrastructure failures should not be disguised as row-quality issues.

## 86. Custom persisters

ImportPersister can call:

~~~text
CRM facade
domain services
Unit of Work
repositories through application services
external integrations
~~~

The framework requires only a PersistResult.

## 87. Update semantics belong to the persister

PersistAction.UPDATED means the application performed an update.

ImportPipeline does not decide:

~~~text
which entity is updated
which fields overwrite
how missing fields behave
what constitutes unchanged data
~~~

## 88. SKIPPED semantics belong to the persister

PersistAction.SKIPPED may represent:

~~~text
unchanged record
business rule
dry-run simulation
unsupported operation
application decision
~~~

The generic report records skipped status only.

## 89. No built-in dry-run flag

Stable V1 ImportPipeline has no dry_run option.

An application can implement simulation through its persister, but that is not
a pipeline-level mode.

## 90. No built-in chunking

There is no chunk_size constructor option.

Chunking can be implemented by custom readers or application orchestration.

## 91. No built-in concurrency

Rows are processed sequentially.

Stable source-order behavior is therefore deterministic.

## 92. Standard-library format adapters

CSV, JSON and JSONL readers use the Python standard library.

Pandas is not required.

## 93. Import and ExternalIdentity example architecture

A repeatable application flow can be:

~~~text
row
 |
 v
normalize external system + ID
 |
 v
find ExternalIdentity
 |
 +--> found
 |      |
 |      v
 |   update or skip owner
 |
 +--> missing
        |
        v
     create Contact
        |
        v
     attach ExternalIdentity
        |
        v
     commit
~~~

The framework supplies the pieces but not one mandatory policy.

## 94. Import vs deduplication

ExternalIdentity answers:

~~~text
Is this the same upstream record?
~~~

Deduplication answers:

~~~text
Do these CRM records likely represent the same real-world entity?
~~~

The ImportPipeline can use both, but they remain distinct concepts.

## 95. Prefer deterministic identity when trustworthy

When a stable external key exists, applications often resolve it before fuzzy
deduplication.

Rows without deterministic identity, or conflicts requiring review, can then
use the richer DeduplicationEngine covered in chapter 19.

This is an application architecture pattern, not hard-coded pipeline behavior.

## Common mistakes

### Expecting a crm.imports facade

Stable V1 import APIs live in pycrmkit.importers.

### Expecting ImportPipeline to create Contacts

Persistence policy belongs to ImportPersister.

### Expecting automatic ExternalIdentity attachment

Compose it explicitly in the persister.

### Using mapping defaults for blank strings

Defaults apply only when the source key is absent.

### Lowercasing every imported value

Normalization must respect field semantics.

### Treating validation_errors as invalid row count

It counts issues, not rows.

### Assuming duplicate source records are automatically removed

Readers preserve duplicates.

### Expecting DuplicateResult.reason in ImportRowResult

The generic report keeps duplicate_entity_id but not reason.

### Treating malformed source syntax as an ordinary invalid row

Reader structural errors propagate.

### Swallowing persistence failures as skipped rows

Deduplication and persistence failures intentionally propagate.

### Calling JSONReader streaming

It materializes the JSON document.

### Assuming retain_row_results=False bounds all memory usage

It only reduces report retention.

### Expecting the whole run to be one transaction

Transaction scope belongs to application persistence.

### Expecting prior committed rows to roll back after a later error

That depends on the persister's transaction design.

### Treating ImportRow as deeply immutable

Its top-level mapping is immutable; nested values are not recursively frozen.

### Reimplementing the entire CRM domain in ImportValidator

Use import validation for source feedback and let the domain remain
authoritative.

### Logging full source records

Import rows may contain personal or sensitive data.

## Testing import applications

Reader tests should cover:

~~~text
source order
empty input
Unicode
malformed syntax
invalid row shape
duplicate rows preserved
stream/path behavior
~~~

Mapping/normalization tests should cover:

~~~text
rename
default
ignore
preserve_unmapped
duplicate targets
normalization order
None handling
failure conversion
~~~

Validation/dedup tests should cover:

~~~text
required fields
multiple issues
predicate checks
duplicate skip
duplicate entity ID
~~~

Persistence tests should cover:

~~~text
created
updated
skipped
domain failure propagation
transaction semantics
ExternalIdentity routing
~~~

Reporting tests should cover:

~~~text
exact counters
issue count vs row count
stages
row numbers
detailed results
summary mode
~~~

## What you learned

You can now explain and use:

- ImportRow;
- ImportReader and IterableReader;
- CSVReader, JSONReader and JSONLReader;
- streaming and materialization boundaries;
- FieldMapping and RecordMapper;
- defaults, ignored fields and preserve_unmapped;
- NormalizationRule and RecordNormalizer;
- strip_text, casefold_text and empty_text_to_none;
- compose_normalizers;
- RequiredFieldsValidator;
- PredicateValidator;
- CompositeValidator;
- ValidationIssue;
- ImportDeduplicator and DuplicateResult;
- ImportPersister;
- PersistAction and PersistResult;
- ImportPipeline execution order;
- row-level map/normalize/validate reporting;
- deduplicate/persist failure propagation;
- ImportReport counters;
- ImportRowResult and ImportRowError;
- validation issue counting;
- detailed vs summary reporting;
- retain_row_results=False;
- application-owned transaction scope;
- explicit ExternalIdentity integration;
- import idempotency as application policy;
- deterministic external identity vs fuzzy deduplication.

## LEVEL 5 in progress

The Data Operations path now contains:

~~~text
17 External Identities
18 Importing Data
~~~

## Next

The next chapter is **19 - Deduplication**.

We will move from the generic duplicate hook to the stable evidence-based engine:

~~~text
ImportRow / CRM entity
        |
        v
CandidateSource
        |
        v
signals
        |
        v
weighted score
        |
        v
DedupDecision
        |
        v
provenance
        |
        v
review / merge
~~~

The next learning question is:

> How does PyCRMKit detect likely duplicates with explainable evidence while
> keeping the final merge decision explicit and reviewable?
