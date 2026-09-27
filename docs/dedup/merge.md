# Merge

PyCRMKit `0.9.0b3` adds conservative, transactional Contact merge execution on
top of the explainable duplicate-detection engine delivered in `0.9.0b2`.

## Execution model

```text
Dedup candidate
      ↓
DedupProvenance
      ↓
Explicit primary Contact
      ↓
MergeService
      ↓
┌───────────────────────────────────────┐
│ one Unit of Work                      │
│                                       │
│ consolidate Contact profile           │
│ reassign activities                   │
│ reassign/end relationships            │
│ union tags                            │
│ resolve custom fields                 │
│ move external identities              │
│ archive duplicate                     │
│ append audit record                   │
└───────────────────────────────────────┘
      ↓
commit
```

If any operation raises before commit, the Unit of Work rolls the entire merge
back. Partial merges are not an observable state.

## Primary selection

The caller must select the primary Contact explicitly:

```python
result = service.merge_contacts(
    primary_id=primary.id,
    duplicate_id=duplicate.id,
    provenance=assessment.provenance,
)
```

The service never chooses a primary record implicitly.

By default a merge also requires `DedupProvenance` whose candidate ID matches
the duplicate and whose decision is `duplicate`. This requirement can be
disabled through `MergePolicy(require_duplicate_provenance=False)` for an
explicit application-controlled/manual workflow.

## Contact profile consolidation

The primary Contact keeps its identity, creation timestamp, status and existing
non-empty scalar values. Missing profile values are filled from the duplicate.

Emails and phones are unioned by their normalized values. Postal addresses are
unioned by their normalized address components.

Metadata is combined with primary-record values winning on key collisions.

If the primary display name was derived from its first/last name, it is
recomputed when the merge fills a missing name component.

## Primary email and phone conflicts

Different primary emails or phones are destructive conflicts by default:

```text
primary email A + duplicate primary email B
                 ↓
              REJECT
```

`MergePolicy` exposes three resolutions:

```text
reject
keep_primary
keep_duplicate
```

The default is `reject` for both primary email and primary phone conflicts.

## Activities

Activities referencing the duplicate as either a participant or a generic
reference are rewritten to the primary Contact.

If the same activity already contains both Contacts, the resulting participant
and reference sets are deduplicated. Existing primary-record participant
metadata is preferred while `is_primary` is preserved when either participant
carried it.

## Relationships

Active relationships involving the duplicate are reassigned to the primary.

A direct relationship between primary and duplicate cannot be rewritten without
creating a self-relationship, so it is ended at merge time instead.

Already-ended relationships remain historical records and are not rewritten.

## Tags

Tags are unioned:

```text
Primary   = {VIP, Customer}
Duplicate = {VIP, Imported}

Result    = {VIP, Customer, Imported}
```

Duplicate assignments are removed after any missing primary assignments are
created.

## Custom fields

Duplicate-only custom-field values are moved to the primary Contact.

When both records contain the same definition and the same value, the primary
value is retained and the duplicate value is removed.

When values disagree, the default policy is conservative:

```text
custom_field_conflict = reject
```

Applications may opt into `keep_primary` or `keep_duplicate`.

## External identities

Every external identity owned by the duplicate is moved to the primary while
preserving:

```text
ExternalIdentity ID
system
external_id
created_at
metadata
```

Only ownership and `updated_at` change.

## Duplicate lifecycle

The duplicate Contact is archived after all owned state has been reassigned.

PyCRMKit does not physically delete the duplicate because the Contact repository
contract provides lifecycle archival rather than destructive deletion. This
also preserves historical references that intentionally remain attached to the
archived record.

## Audit and provenance

A successful merge appends one `contact.merged` audit entry containing:

```text
duplicate Contact ID
merge statistics
selected conflict policies
dedup score
dedup decision
matched signal names
conflict signal/severity summary
```

Matched email/phone/address values are deliberately not copied into the audit
record. The full `DedupProvenance` object remains attached to `MergeResult`,
while persisted audit evidence is minimized to avoid unnecessary PII
duplication.

## Observable statistics

`MergeResult.statistics` exposes:

```text
activities_reassigned
relationships_reassigned
relationships_ended
tags_added
custom_fields_moved
custom_field_conflicts
external_identities_moved
```

## Scope boundary

`0.9.0b3` provides Contact merge execution. It does not add organization merge
execution or a fully integrated import → detect → review → merge → export
application scenario.

That cross-capability scenario is the next milestone:

`0.9.0rc1 — Data Operations E2E`.
