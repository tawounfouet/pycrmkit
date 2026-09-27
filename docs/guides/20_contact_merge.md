# Contact Merge

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 5 - Data Operations**.

Chapter 19 ended with an explainable duplicate candidate. Chapter 20 crosses a
different boundary: explicit, transactional reconciliation of two Contact
records.

The stable V1 execution model is:

~~~text
DedupProvenance
      |
      v
explicit primary Contact
explicit duplicate Contact
      |
      v
MergePolicy
      |
      v
MergeService
      |
      +--> consolidate Contact profile
      +--> reassign Activities
      +--> reassign/end Relationships
      +--> union Tags
      +--> resolve Custom Fields
      +--> move External Identities
      +--> archive duplicate
      +--> append AuditEntry
      |
      v
one Unit of Work commit
      |
      v
MergeResult
~~~

The critical design principle is:

> Detection may suggest a duplicate, but merge execution never silently chooses
> the surviving Contact.

## What you will build

You will learn to:

- select primary and duplicate Contacts explicitly;
- understand MergeResolution and MergePolicy;
- use the pure merge_contact_profile function;
- understand scalar profile coalescing;
- understand email, phone and address union rules;
- resolve competing primary email and phone values;
- understand metadata precedence;
- understand display-name recomputation;
- validate DedupProvenance;
- understand manual merge policy;
- execute MergeService in one Unit of Work;
- understand Activity reassignment and collapse;
- understand Relationship reassignment and direct-link closure;
- union Tags;
- move or resolve Custom Fields;
- preserve and move ExternalIdentity records;
- archive rather than delete the duplicate Contact;
- inspect MergeStatistics;
- inspect the privacy-minimized AuditEntry;
- understand rollback guarantees;
- distinguish Audit from Domain Events;
- prepare for Data Export.

## 1. Merge is destructive reconciliation

A merge changes ownership of CRM state.

It can alter:

~~~text
Contact profile
Activities
Relationships
Tags
Custom Fields
External Identities
Contact lifecycle state
Audit history
~~~

For that reason, stable V1 uses conservative defaults.

## 2. Stable public merge surface

The relevant public API is:

~~~text
MergeResolution
MergePolicy
MergeStatistics
MergeResult
merge_contact_profile
MergeService
~~~

DedupProvenance from chapter 19 is the default authorization evidence for
automatic duplicate-driven merge.

## 3. There is no crm.contacts.merge facade operation

Stable V1 merge execution is exposed through MergeService.

The caller supplies a UnitOfWork factory and explicit Contact IDs.

That keeps a destructive cross-repository workflow outside the lightweight
Contact facade.

## 4. Explicit primary selection

The caller must provide:

~~~python
result = service.merge_contacts(
    primary_id=primary.id,
    duplicate_id=duplicate.id,
    provenance=assessment.provenance,
)
~~~

The service never chooses the primary Contact based on score, age, completeness
or candidate ordering.

## 5. Primary and duplicate must differ

Passing the same ContactId for both roles raises:

~~~text
ValidationError
code = merge.contact.same_record
~~~

This validation exists both in MergeService and the pure profile merge helper.

## 6. Primary identity survives

merge_contact_profile returns a replacement of the primary Contact.

Therefore the merged record preserves the primary's:

~~~text
ContactId
created_at
status
archived_at state
~~~

subject to Contact invariants.

The duplicate identity is not reused as the survivor.

## 7. Archived Contacts cannot participate as mutable merge inputs

The pure helper calls ensure_mutable on both Contacts.

An archived Contact therefore fails with:

~~~text
InvalidStateError
code = contact.archived
~~~

Stable merge is intended for mutable records.

## 8. MergeResolution

Stable conflict resolution values are:

~~~text
reject
keep_primary
keep_duplicate
~~~

They apply to the supported destructive conflict classes.

## 9. MergePolicy defaults

The default policy is:

~~~text
primary_email_conflict   = reject
primary_phone_conflict   = reject
custom_field_conflict    = reject
require_duplicate_provenance = true
~~~

Conservative behavior is opt-out, not opt-in.

## 10. String-compatible policy values

MergePolicy normalizes its three resolution fields through MergeResolution.

That means enum-compatible string values can be accepted and converted at
construction time.

## 11. Pure profile merge

merge_contact_profile performs only Contact aggregate consolidation.

It does not:

~~~text
open a Unit of Work
save repositories
move Activities
move Relationships
move Tags
move Custom Fields
move External Identities
archive the duplicate
write Audit
~~~

This pure layer is useful for deterministic policy testing.

## 12. Merge timestamp

The caller supplies an explicit at datetime to merge_contact_profile.

The returned primary replacement uses:

~~~text
updated_at = at
~~~

MergeService obtains this timestamp from its injected Clock.

## 13. Scalar profile coalescing

For first_name, last_name, owner_id and source, stable V1 follows:

~~~text
primary non-empty value wins
otherwise use duplicate value
~~~

Conceptually:

~~~python
first_name = primary.first_name or duplicate.first_name
last_name = primary.last_name or duplicate.last_name
owner_id = primary.owner_id or duplicate.owner_id
source = primary.source or duplicate.source
~~~

## 14. Primary scalar values are not overwritten merely because duplicate differs

If both Contacts already carry a non-empty source, owner or name component, the
primary value remains.

MergePolicy does not currently expose scalar conflict resolution for those
fields.

## 15. Metadata merge

Metadata begins from duplicate metadata and is then updated with primary
metadata.

Therefore:

~~~text
duplicate-only keys survive
primary-only keys survive
key collision -> primary value wins
~~~

## 16. Metadata example

~~~text
Primary:
{
  owner_note: "primary",
  shared: "primary"
}

Duplicate:
{
  source_note: "duplicate",
  shared: "duplicate"
}

Merged:
{
  source_note: "duplicate",
  shared: "primary",
  owner_note: "primary"
}
~~~

## 17. Display-name behavior

The merge distinguishes a derived primary display name from an explicit one.

It computes what the primary display name would be from its current first and
last name.

If the stored primary display_name equals that derived value, the merged
display name is recomputed after filling missing name components.

## 18. Derived display-name refresh

Example:

~~~text
Primary:
first_name = None
last_name = Lovelace
display_name = Lovelace

Duplicate:
first_name = Ada

Merged:
first_name = Ada
last_name = Lovelace
display_name = Ada Lovelace
~~~

## 19. Explicit primary display name is preserved

If the primary display_name differs from its derived first/last-name value, it
is treated as explicit.

Stable V1 then keeps:

~~~text
primary.display_name
or duplicate.display_name if primary is absent
~~~

## 20. Email union

Emails are unioned by normalized email value.

The order is:

~~~text
primary emails first
then duplicate-only emails
~~~

Equivalent normalized addresses collapse to one entry.

## 21. Primary email selection

Before union, the merge identifies each Contact's primary email by normalized
value.

If the primary has no primary email, the duplicate primary can become primary.

If both point to the same normalized email, no conflict exists.

## 22. Conflicting primary emails

If both Contacts have different primary emails, default behavior is:

~~~text
merge.contact.email_primary.conflict
~~~

with ConflictError.

## 23. KEEP_PRIMARY email resolution

With:

~~~python
MergePolicy(
    primary_email_conflict=MergeResolution.KEEP_PRIMARY,
)
~~~

both unique email addresses remain, but the primary Contact's previous primary
email keeps primary status.

## 24. KEEP_DUPLICATE email resolution

With:

~~~python
MergePolicy(
    primary_email_conflict=MergeResolution.KEEP_DUPLICATE,
)
~~~

both email addresses remain and the duplicate's former primary email becomes
the merged primary email.

## 25. Phone union

Phone behavior mirrors email behavior.

Normalized phone values are unioned and primary selection is governed by:

~~~text
primary_phone_conflict
~~~

## 26. Primary phone conflict code

Default rejection raises:

~~~text
merge.contact.phone_primary.conflict
~~~

## 27. Address union

Addresses are deduplicated by a case-insensitive structural key containing:

~~~text
line1
line2
postal_code
city
region
country_code
~~~

## 28. Address primary selection

If the primary Contact already has a primary address, it remains the selected
primary address.

Otherwise the duplicate's primary address can become primary.

There is no configurable primary-address conflict policy in stable V1.

## 29. Address comparison is not the chapter-19 DedupProfile address matcher

Contact merge uses Contact Address components and a casefolded structural key.

It does not call DedupProfile or StandardSignalMatcher.

Detection policy and merge reconciliation policy remain separate layers.

## 30. Provenance requirement

MergeService validates provenance before opening the merge transaction.

By default:

~~~text
provenance is required
candidate_entity_id must equal duplicate ContactId
decision must be duplicate
no blocking conflict may be present
~~~

## 31. Missing provenance

Default policy raises:

~~~text
ValidationError
code = merge.provenance.required
~~~

## 32. Candidate mismatch

If provenance points to another candidate:

~~~text
ValidationError
code = merge.provenance.candidate_mismatch
~~~

## 33. Decision must be DUPLICATE

With default require_duplicate_provenance=True, REVIEW or another non-duplicate
decision raises:

~~~text
ConflictError
code = merge.provenance.decision.invalid
~~~

The error context includes the decision value.

## 34. Blocking provenance conflicts always matter when provenance is supplied

If provenance contains any ConflictSeverity.BLOCKING item, merge is rejected:

~~~text
ConflictError
code = merge.provenance.blocking_conflict
~~~

The context contains the sorted blocking signal names.

This check happens before the optional provenance requirement is relaxed.

## 35. Manual/application-controlled merge

Applications can opt into:

~~~python
MergePolicy(
    require_duplicate_provenance=False,
)
~~~

This allows a merge with no provenance.

It also allows supplied provenance whose decision is not DUPLICATE.

## 36. Manual mode does not disable all provenance safeguards

When provenance is supplied even under manual mode:

~~~text
candidate ID must still match duplicate
blocking conflicts are still rejected
~~~

Only the requirement that provenance exist and carry a DUPLICATE decision is
disabled.

## 37. MergeService dependencies

MergeService receives:

~~~text
uow_factory
id_factory
clock
policy
~~~

Defaults:

~~~text
UUID4Factory
SystemClock
MergePolicy()
~~~

## 38. Per-call policy override

merge_contacts accepts a policy argument.

If supplied, it overrides the service-level policy for that merge only.

## 39. One Unit of Work

After provenance validation and timestamp creation, MergeService opens exactly
one UnitOfWork and performs all persisted merge stages inside it.

Conceptually:

~~~text
with uow_factory() as uow:
    load primary
    load duplicate
    merge profile
    save primary
    reassign activities
    reassign relationships
    merge tags
    merge custom fields
    move external identities
    archive duplicate
    append audit
    commit
~~~

## 40. Atomicity

If any stage raises before commit, the UnitOfWork exits without publishing its
working state.

For transactional adapters, partial merge state must not become observable.

The MemoryUnitOfWork qualification explicitly verifies rollback after a late
custom-field conflict.

## 41. Contact profile is saved before linked-state migration inside the transaction

The implementation saves the consolidated primary before Activities,
Relationships, Tags and Custom Fields are processed.

This is safe because all those changes remain uncommitted until the final
UnitOfWork commit.

## 42. Activity lookup

Activities are collected in two ways:

~~~text
participant == duplicate Contact
reference == duplicate Contact
~~~

The service combines them by Activity ID so an Activity matching both queries is
processed once.

## 43. Activity participant rewrite

Every participant reference equal to the duplicate Contact becomes the primary
Contact reference.

Other participant references remain unchanged.

## 44. Participant collapse

If rewriting creates two participant entries with the same EntityReference, the
entries collapse into one.

Stable implementation behavior:

~~~text
role = current role if present, otherwise later participant role
is_primary = logical OR
~~~

Because "current" depends on original participant ordering, applications should
not infer a stronger semantic precedence rule than this actual V1 algorithm.

## 45. Activity generic-reference rewrite

Every Activity reference equal to the duplicate becomes the primary.

Duplicate references are then collapsed so the resulting reference tuple
contains unique references in encountered order.

## 46. Activity timestamp

Reassigned Activities receive:

~~~text
updated_at = merge timestamp
~~~

## 47. activities_reassigned statistic

The statistic counts the number of distinct Activities rewritten.

An Activity found by both participant and reference queries counts once.

## 48. Relationship lookup

The service searches Relationships involving the duplicate Contact endpoint.

Stable documentation defines this operation over active relationships.

## 49. Relationship reassignment

For a normal Relationship involving duplicate and some third entity:

~~~text
duplicate endpoint
-> primary endpoint
~~~

The Relationship ID and other relationship state survive.

updated_at becomes the merge timestamp.

## 50. Direct primary-to-duplicate Relationships

If a Relationship already connects primary and duplicate, rewriting duplicate
to primary would create a self-relationship.

Stable V1 ends that Relationship at merge time instead.

## 51. relationships_reassigned

Counts Relationships whose duplicate endpoint is rewritten to primary.

## 52. relationships_ended

Counts direct primary/duplicate Relationships ended to avoid self-reference.

## 53. Historical ended Relationships

Stable merge documentation preserves already-ended Relationships as historical
records rather than rewriting them.

Merge is focused on active ownership/state reconciliation.

## 54. Tag union

Primary Tag assignments are collected first.

For every duplicate Tag:

~~~text
already on primary
-> do not create another assignment

missing from primary
-> create assignment for primary

then remove duplicate assignment
~~~

## 55. tags_added

This statistic counts new primary Tag assignments created.

It does not count duplicate assignments merely removed.

## 56. New TagAssignment IDs

When a missing duplicate Tag is added to primary, MergeService uses its injected
IDFactory to create a new TagAssignmentId.

The Tag entity itself is reused.

## 57. Custom Field merge

Values are compared by CustomFieldDefinition ID.

There are three major paths.

## 58. Duplicate-only Custom Field

If primary has no value for a definition:

~~~text
remove duplicate-owned value
replace its entity with primary
set updated_at to merge time
save it
custom_fields_moved += 1
~~~

The existing CustomFieldValue identity is preserved by replace.

## 59. Equal Custom Field values

If both Contacts have the same definition and equal value:

~~~text
keep primary value
remove duplicate value
no conflict
no moved increment
~~~

## 60. Conflicting Custom Field values

If values differ:

~~~text
custom_field_conflicts += 1
~~~

Then MergePolicy.custom_field_conflict determines behavior.

## 61. REJECT Custom Field policy

Default behavior raises:

~~~text
ConflictError
code = merge.custom_field.conflict
~~~

Context includes the definition ID.

Because this occurs inside the same UnitOfWork, earlier merge mutations must
roll back.

## 62. KEEP_PRIMARY Custom Field policy

The primary value remains.

The duplicate value is removed.

The conflict count still increments.

The moved count does not increment for that conflict.

## 63. KEEP_DUPLICATE Custom Field policy

Both existing ownership records are removed, then the duplicate value object is
re-owned by primary and saved.

Result:

~~~text
custom_field_conflicts += 1
custom_fields_moved += 1
~~~

## 64. ExternalIdentity transfer

Every ExternalIdentity owned by the duplicate Contact is collected.

For each identity:

~~~text
remove old ownership record
replace:
  updated_at = merge timestamp
  entity_type = contact
  entity_id = primary ContactId
save
~~~

## 65. ExternalIdentity identity and provider key are preserved

Transfer preserves:

~~~text
ExternalIdentity.id
system
external_id
created_at
metadata
~~~

Only owner reference and updated_at change.

## 66. Why this matters for future imports

After merge, provider records previously attached to the duplicate now resolve
to the primary Contact.

The archived duplicate no longer owns those external keys.

## 67. external_identities_moved

Counts transferred ExternalIdentity records.

## 68. Duplicate Contact is archived

After linked state is reconciled, MergeService calls:

~~~text
uow.contacts.archive(duplicate_id, now)
~~~

The duplicate is not physically deleted.

## 69. Archive preserves historical identity

The duplicate Contact remains addressable through the repository, now with:

~~~text
status = archived
archived_at = merge timestamp
updated_at = merge timestamp
~~~

This protects historical references that intentionally remain on the old
record.

## 70. Archived duplicate becomes immutable

Normal Contact mutation is rejected after archival through the Contact
aggregate's ensure_mutable rule.

## 71. MergeStatistics

A committed MergeResult includes:

~~~text
activities_reassigned
relationships_reassigned
relationships_ended
tags_added
custom_fields_moved
custom_field_conflicts
external_identities_moved
~~~

## 72. MergeStatistics.as_dict

The result can be converted to the same seven integer counters.

This is useful for reporting and audit.

## 73. Statistics describe mutations, not every inspected item

Examples:

~~~text
existing Tag already shared
-> not tags_added

equal Custom Field removed from duplicate
-> not custom_fields_moved

direct primary/duplicate Relationship
-> relationships_ended, not reassigned
~~~

## 74. Audit entry

A successful merge appends one immutable AuditEntry with:

~~~text
action = contact.merged
entity_type = contact
entity_id = primary ContactId
actor_id = caller value
correlation_id = caller value
changes = minimized merge evidence
~~~

## 75. Audit is append-oriented

AuditService creates a new typed AuditEntryId and appends the entry.

The merge does not mutate an earlier audit record.

## 76. Audit policy snapshot

changes contains selected conflict policies:

~~~text
primary_email_conflict
primary_phone_conflict
custom_field_conflict
~~~

require_duplicate_provenance is not currently copied into the audit policy
mapping.

## 77. Audit statistics

The complete MergeStatistics.as_dict output is included in changes.

This records what the committed merge mutated.

## 78. Audit duplicate ID

changes includes:

~~~text
duplicate_id
~~~

so the surviving Contact audit can identify which record was archived.

## 79. Provenance audit minimization

When provenance is supplied, audit stores:

~~~text
candidate_entity_id
score
decision
matched signal names
conflict signal
conflict severity
conflict key
~~~

## 80. Full matched values are not copied into audit

The audit intentionally omits:

~~~text
matched email values
phone values
address values
incoming conflict values
candidate conflict values
~~~

This reduces unnecessary PII duplication.

## 81. Full provenance remains on MergeResult

MergeResult.provenance references the full supplied DedupProvenance.

The caller can use it immediately for controlled review or application logic.

Persisted audit evidence is deliberately smaller.

## 82. contact.merged is not a DomainEvent in MergeService

The string contact.merged is used as AuditEntry.action.

MergeService does not stage a DomainEvent through UnitOfWork.add_event.

Applications should not assume a merge automatically enters the Domain Event
bus or Webhook pipeline.

## 83. MergeResult

The committed result contains:

~~~text
primary
duplicate
statistics
audit_entry
provenance
~~~

primary is the merged survivor.

duplicate is the archived duplicate returned by repository archive.

## 84. Actor and correlation context

merge_contacts accepts optional:

~~~text
actor_id
correlation_id
~~~

They are copied into the AuditEntry.

This lets application orchestration connect the destructive action to an
operator/request trace.

## 85. Provenance validation happens before repository loading

MergeService validates:

~~~text
same ID check
provenance candidate
blocking conflicts
required decision
~~~

before opening the UnitOfWork and loading Contacts.

This avoids unnecessary mutation work for invalid merge authorization evidence.

## 86. NotFound behavior

Once the UnitOfWork is open, primary and duplicate are loaded through the Contact
repository get contract.

Missing records therefore follow repository NotFoundError semantics.

MergeService does not invent a special merge-specific not-found type.

## 87. Rollback example

Suppose the service has already:

~~~text
saved merged profile
rewritten a Tag assignment
~~~

and then discovers:

~~~text
primary custom field = gold
duplicate custom field = silver
policy = reject
~~~

The custom-field conflict raises before commit.

MemoryUnitOfWork discards all working mutations.

Observable state remains pre-merge.

## 88. No partial audit on rollback

Because AuditEntry creation also happens inside the same UnitOfWork before
commit, a failed merge does not leave behind a committed contact.merged audit
record.

## 89. Profile conflict can fail before linked-state rewrites

A primary email or phone conflict is discovered during merge_contact_profile.

Those failures happen before the merged profile is saved.

## 90. Custom Field conflict is a useful late-failure atomicity test

The repository qualification deliberately uses a custom-field conflict because
earlier stages have already mutated the transactional working state.

Successful rollback therefore demonstrates more than an early validation
failure.

## 91. Merge is not idempotent retry by default

After a successful merge, the duplicate is archived.

A second normal merge attempt with the same pair encounters immutable archived
state rather than replaying the previous MergeResult.

Applications that need retry-safe orchestration should persist their own
operation identity/result around this destructive command.

## 92. Merge does not hard-delete

Stable V1 public facades do not expose generic purge/hard-delete operations.

Merge follows the same lifecycle safety model by archiving the duplicate.

## 93. Merge scope is Contact-only

Stable V1 MergeService implements Contact merge.

It does not provide:

~~~text
Organization merge
Lead merge
Opportunity merge
generic EntityReference merge
~~~

Those would require their own domain policies.

## 94. No automatic primary choice from DeduplicationEngine

Even if evaluate returns one score-100 candidate, MergeService still requires:

~~~text
primary_id
duplicate_id
~~~

explicitly.

Candidate detection and survivor selection are intentionally different
decisions.

## 95. Detection-to-merge application flow

A safe application flow is:

~~~text
incoming / duplicate Contact
        |
        v
DeduplicationEngine.evaluate
        |
        v
review evidence
        |
        v
explicitly choose primary
        |
        v
MergeService.merge_contacts
        |
        v
AuditEntry + archived duplicate
~~~

## 96. Complete profile-only example

~~~python
merged = merge_contact_profile(
    primary,
    duplicate,
    at=clock.now(),
    policy=MergePolicy(
        primary_email_conflict=MergeResolution.KEEP_PRIMARY,
    ),
)
~~~

This returns a Contact value but performs no persistence.

## 97. Complete service example

~~~python
service = MergeService(
    lambda: MemoryUnitOfWork(store),
    clock=clock,
)

result = service.merge_contacts(
    primary_id=primary.id,
    duplicate_id=duplicate.id,
    provenance=assessment.provenance,
    actor_id="operator-1",
    correlation_id="merge-001",
)
~~~

After successful commit:

~~~text
result.primary
-> surviving merged Contact

result.duplicate
-> archived Contact

result.audit_entry.action
-> contact.merged
~~~

## 98. Manual merge example

For an application-controlled workflow without dedup provenance:

~~~python
service = MergeService(
    lambda: MemoryUnitOfWork(store),
    policy=MergePolicy(
        require_duplicate_provenance=False,
    ),
)

result = service.merge_contacts(
    primary_id=primary.id,
    duplicate_id=duplicate.id,
    actor_id="operator-1",
)
~~~

The caller now owns the decision to authorize that merge.

## 99. Conflict policy example

~~~python
policy = MergePolicy(
    primary_email_conflict=MergeResolution.KEEP_PRIMARY,
    primary_phone_conflict=MergeResolution.KEEP_DUPLICATE,
    custom_field_conflict=MergeResolution.KEEP_PRIMARY,
)
~~~

This policy is explicit enough to audit and test.

## 100. Privacy boundary

The full MergeResult can contain full DedupProvenance and merged Contact state.

Treat it as sensitive application data.

The persisted AuditEntry is intentionally minimized, but still includes entity
IDs and operational evidence.

## Common mistakes

### Treating a duplicate decision as permission to choose the survivor automatically

MergeService requires explicit primary_id and duplicate_id.

### Calling merge without provenance under default policy

It fails with merge.provenance.required.

### Assuming manual mode ignores bad supplied provenance

Candidate mismatch and blocking conflicts are still rejected.

### Treating REVIEW provenance as sufficient under default policy

Default merge requires decision=duplicate.

### Ignoring blocking conflicts because score is 100

Blocking provenance conflicts are rejected before the transaction.

### Expecting scalar values from duplicate to overwrite populated primary values

Scalar coalescing is primary-first.

### Expecting metadata from duplicate to win collisions

Primary metadata wins key collisions.

### Assuming email/phone union automatically picks one primary when both differ

Default policy rejects competing primary values.

### Assuming addresses have a configurable primary conflict policy

Stable V1 keeps the primary Contact's primary address when present.

### Treating participant collapse as a universal primary-record-role preference

The actual algorithm preserves the current non-empty role and ORs is_primary;
original participant order matters.

### Rewriting a direct primary/duplicate Relationship

The service ends it to avoid a self-relationship.

### Counting all duplicate Tags as tags_added

Only newly created primary assignments count.

### Assuming equal Custom Field values count as moved

The duplicate value is removed without incrementing moved.

### Forgetting that KEEP_DUPLICATE custom-field conflict increments both conflict and moved

The duplicate value is actually re-owned by primary.

### Expecting ExternalIdentity records to be recreated

Their IDs/provider keys are preserved; ownership moves.

### Hard-deleting the duplicate

Stable merge archives it.

### Expecting a contact.merged DomainEvent

MergeService records an AuditEntry action, not a DomainEvent.

### Assuming a failed late merge can leave partial state

All merge mutations occur inside one Unit of Work.

### Retrying a successful merge as if it were automatically idempotent

The duplicate is archived; stable V1 does not return a cached previous result.

## Testing Contact Merge

Profile tests should cover:

~~~text
same-record rejection
missing scalar coalescing
derived display-name refresh
metadata precedence
email union
phone union
address union
primary email conflict
primary phone conflict
keep_primary
keep_duplicate
~~~

Provenance tests should cover:

~~~text
missing provenance
candidate mismatch
review decision
blocking conflict
manual provenance-disabled mode
~~~

Cross-repository tests should cover:

~~~text
Activity participant reassignment
Activity reference reassignment
participant/reference collapse
Relationship reassignment
direct Relationship closure
Tag union
Custom Field move
Custom Field equality
Custom Field conflict policies
ExternalIdentity ownership transfer
duplicate archival
~~~

Transaction tests should force a late conflict and verify:

~~~text
primary profile unchanged
duplicate still active
Tag assignments unchanged
Custom Fields unchanged
no merge AuditEntry committed
~~~

Audit tests should cover:

~~~text
contact.merged action
actor_id
correlation_id
duplicate_id
statistics
policy snapshot
minimized provenance
absence of matched PII values
~~~

## What you learned

You can now explain and use:

- MergeResolution;
- MergePolicy;
- conservative merge defaults;
- merge_contact_profile;
- primary-first scalar coalescing;
- display-name refresh;
- metadata precedence;
- normalized email and phone union;
- primary contact-point conflict policies;
- structural address union;
- provenance requirement;
- provenance candidate validation;
- blocking conflict validation;
- manual merge policy;
- MergeService;
- one-Unit-of-Work atomicity;
- Activity reassignment;
- participant/reference collapse;
- Relationship reassignment;
- direct Relationship closure;
- Tag union;
- Custom Field conflict handling;
- ExternalIdentity ownership transfer;
- duplicate archival;
- MergeStatistics;
- privacy-minimized AuditEntry;
- full provenance retention in MergeResult;
- the distinction between Audit and Domain Events;
- rollback guarantees;
- Contact-only merge scope.

## LEVEL 5 in progress

The Data Operations path now contains:

~~~text
17 External Identities
18 Importing Data
19 Deduplication
20 Contact Merge
~~~

We can now ingest external data, identify likely duplicate Contacts and reconcile
a reviewed duplicate transactionally.

## Next

The next chapter is **21 - Exporting Data**.

The Data Operations loop will become:

~~~text
External Identity
      |
      v
Import
      |
      v
Deduplicate
      |
      v
Merge
      |
      v
Export
~~~

The next learning question is:

> How does PyCRMKit export CRM data deterministically to CSV, JSON and JSONL
> while preserving portable field mapping, pagination and privacy boundaries?
