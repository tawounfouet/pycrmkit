# Deduplication

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 5 - Data Operations**.

Chapter 18 introduced the generic ImportDeduplicator hook. Chapter 19 replaces
that placeholder with the stable V1 evidence-based duplicate detection engine.

The stable flow is:

~~~text
Incoming ImportRow
        |
        v
CandidateSource
        |
        v
CandidateRecord
        |
        v
DedupProfile
        |
        +--> exact normalized matches
        +--> contradictory evidence
        |
        v
DedupScorePolicy
        |
        v
DedupDecision
        |
        v
DedupProvenance
~~~

The central rule is conservative: detection produces evidence and a decision,
but it does not merge CRM records.

## What you will build

You will learn to:

- represent existing CRM records with CandidateRecord;
- provide candidates through CandidateSource;
- normalize all seven stable signals;
- understand exact normalized matching;
- configure weights and thresholds;
- interpret no_match, review, duplicate and conflict;
- retain warning and blocking conflicts;
- inspect DedupProvenance;
- understand deterministic candidate ordering;
- use DeduplicationEngine as an ImportDeduplicator;
- understand the exactly-one-duplicate auto-detection rule;
- prepare for explicit Contact Merge.

## 1. Detection is not merge

PyCRMKit separates:

~~~text
Does this record look like an existing record?
~~~

from:

~~~text
Should two CRM records be merged?
~~~

Chapter 19 answers the first question. Chapter 20 performs explicit merge
execution.

## 2. Stable public detection surface

The important V1 types are:

~~~text
CandidateRecord
CandidateSource
InMemoryCandidateSource
CandidateAssessment
DeduplicationEngine

DedupProfile
DedupSignal
SignalMatch
StandardSignalMatcher
normalize_text

ConflictSeverity
DedupConflict
StandardConflictDetector

DEFAULT_SIGNAL_WEIGHTS
DedupDecision
DedupScorePolicy
ScoreResult

DedupProvenance
~~~

## 3. CandidateRecord

A candidate is an existing entity plus matching evidence:

~~~python
candidate = CandidateRecord(
    "contact-123",
    {
        "email": "ada@example.com",
        "full_name": "Ada Lovelace",
        "organization": "Analytical Engines",
    },
)
~~~

CandidateRecord strips entity_id and rejects an empty identifier with:

~~~text
dedup.candidate.entity_id.empty
~~~

## 4. Candidate values and profile

CandidateRecord copies values into a top-level immutable mapping and computes:

~~~text
DedupProfile.from_mapping(values)
~~~

once during construction.

Nested mutable values are not recursively frozen.

## 5. CandidateSource

The protocol is:

~~~python
def candidates(
    self,
    row: ImportRow,
) -> Iterable[CandidateRecord]:
    ...
~~~

The source receives the incoming row so a production implementation can
pre-filter candidates before scoring.

## 6. InMemoryCandidateSource

The built-in in-memory source returns its complete tuple of records.

It is ideal for tests and examples. Production applications can implement
repository-backed or search-backed CandidateSource strategies.

## 7. Seven stable signals

DedupSignal contains:

~~~text
email
phone
full_name
organization
address
external_identity
custom_identifier
~~~

## 8. DedupProfile

A normalized profile stores:

~~~text
emails
phones
full_name
organization
addresses
external_identities
custom_identifiers
~~~

Collection signals use frozenset values, so duplicate equivalent values inside
one profile are collapsed.

## 9. Email extraction

Email evidence uses the first non-None value among:

~~~text
normalized_email
email
emails
~~~

Email normalization reuses the Contact-domain normalize_email contract.

Accepted source shapes include a string, iterable of strings, or mappings with
normalized/value string fields.

## 10. Phone extraction

Phone evidence uses:

~~~text
normalized_phone
phone
phones
~~~

and reuses Contact-domain normalize_phone.

## 11. Full-name extraction

Full-name evidence first checks:

~~~text
full_name
display_name
~~~

If neither yields a usable string, first_name and last_name are joined from
their available non-blank parts.

## 12. normalize_text

Human text normalization performs:

~~~text
Unicode NFKC
trim
collapse repeated whitespace
casefold
~~~

It is used for full names, organization text, address text and custom identifier
namespaces.

## 13. Exact equality after normalization

Stable V1 does not use fuzzy string matching.

~~~text
"Ada   Lovelace"
" ada lovelace "
~~~

normalize to the same value.

A typo such as a different spelling remains different.

## 14. Organization extraction

Organization evidence checks, in order:

~~~text
organization_id
organization
organization_name
company
~~~

The first non-None usable string is normalized with normalize_text.

The engine compares evidence; it does not load an Organization aggregate.

## 15. Address extraction

Address evidence checks:

~~~text
address
addresses
~~~

A plain string uses normalize_text.

A mapping uses the ordered fields:

~~~text
line1
line2
postal_code
city
region
country_code
~~~

and joins normalized non-empty parts with a pipe separator.

## 16. Address scope boundary

Stable V1 does not geocode, calculate distance, standardize addresses through an
external database or use fuzzy address similarity.

Matching remains deterministic normalized equality.

## 17. External identity extraction

External identity evidence comes from:

~~~text
external_identity
external_identities
~~~

Each usable mapping needs string fields system and external_id.

The engine reuses:

~~~text
normalize_external_system
normalize_external_id
~~~

from chapter 17.

## 18. External ID case remains provider-owned

External system names normalize and case-fold.

External IDs preserve their provider-defined case.

This rule remains consistent between ExternalIdentity storage and deduplication.

## 19. Custom identifiers

custom_identifiers is a mapping such as:

~~~python
{
    "customer_number": "C-001",
    "member_id": "M-42",
}
~~~

Only string keys and values participate.

Namespace keys use normalize_text.

Identifier values use Unicode NFKC plus trim and preserve case.

## 20. Alias precedence is first non-None

Profile extraction selects the first alias whose value is not None.

It does not keep searching because that selected value happens to be blank.

Canonical field preparation therefore matters.

For predictable behavior, feed clean mappings into the dedup engine.

## 21. StandardSignalMatcher

The matcher compares an incoming DedupProfile with a candidate DedupProfile and
returns SignalMatch evidence.

All matching is exact over normalized representations.

## 22. No fuzzy or probabilistic matching

Stable V1 does not use:

~~~text
edit distance
phonetic algorithms
embeddings
LLMs
vector similarity
probabilistic inference
~~~

This is a deliberate auditable baseline.

## 23. Collection signal matches

For emails, phones and addresses, every exact set intersection value becomes a
SignalMatch.

For external identities and custom identifiers, every exact namespaced pair in
the intersection becomes a SignalMatch.

## 24. Scalar matches

FULL_NAME and ORGANIZATION produce one SignalMatch when both sides contain the
same normalized value.

## 25. SignalMatch

Positive evidence contains:

~~~text
signal
value
key
~~~

key is normally None.

For namespaced evidence it contains:

~~~text
external identity system
or
custom identifier namespace
~~~

## 26. Default weights

Stable weights are:

~~~text
external identity   100
custom identifier   100
email                70
phone                60
full name            25
organization         15
address              20
~~~

## 27. Scoring uses unique signal types

The score is based on the set of matched DedupSignal types.

Therefore:

~~~text
two matching emails
still contribute 70 total

three matching addresses
still contribute 20 total
~~~

The detailed matches remain in provenance, but evidence multiplicity does not
inflate the score.

## 28. Score cap

Weights are added and then capped:

~~~text
score = min(100, weighted total)
~~~

A raw total above 100 still reports score 100.

## 29. Default thresholds

~~~text
review_threshold    = 50
duplicate_threshold = 100
~~~

Without a blocking conflict:

~~~text
0-49   -> no_match
50-99  -> review
100    -> duplicate
~~~

## 30. Default examples

~~~text
email only
70
-> review

phone only
60
-> review

full name only
25
-> no_match

email + full name
95
-> review

email + full name + organization
110 capped to 100
-> duplicate

external identity
100
-> duplicate

custom identifier
100
-> duplicate
~~~

## 31. Configurable thresholds

~~~python
policy = DedupScorePolicy(
    review_threshold=60,
    duplicate_threshold=80,
)
~~~

Thresholds must satisfy:

~~~text
0 <= review <= duplicate <= 100
~~~

Invalid configuration raises:

~~~text
dedup.threshold.invalid
~~~

## 32. Configurable weights

Applications may pass a custom weight mapping.

Weights must be non-negative.

Negative values raise:

~~~text
dedup.weight.invalid
~~~

A signal omitted from a custom weight mapping contributes zero.

## 33. ScoreResult

Scoring returns:

~~~text
score
decision
matched_signals
~~~

matched_signals is the unique set of signal types that contributed evidence.


## 34. Conflicts are separate evidence

Positive matches and contradictory evidence are both retained.

A candidate can simultaneously have a high positive score and warning
conflicts.

StandardConflictDetector does not erase matches.

## 35. ConflictSeverity

Stable severities:

~~~text
warning
blocking
~~~

## 36. DedupConflict

A conflict contains:

~~~text
signal
severity
key
incoming_values
candidate_values
~~~

This preserves explainable contradictory evidence.

## 37. Email conflict

If both sides contain email evidence but have no normalized intersection:

~~~text
EMAIL
severity = warning
~~~

## 38. Phone conflict

If both sides contain phone evidence but no normalized intersection:

~~~text
PHONE
severity = warning
~~~

## 39. Full-name conflict

Two present but unequal normalized full names produce:

~~~text
FULL_NAME
severity = warning
~~~

## 40. Organization conflict

Two present but unequal normalized organizations produce:

~~~text
ORGANIZATION
severity = warning
~~~

## 41. External identity conflict

External identities are grouped by normalized system.

If incoming and candidate both have identities for the same system but no
external-ID intersection:

~~~text
EXTERNAL_IDENTITY
severity = warning
key = system
~~~

## 42. Custom identifier conflict

Custom identifiers are grouped by normalized namespace.

If both sides contain the same namespace but no identifier intersection:

~~~text
CUSTOM_IDENTIFIER
severity = blocking
key = namespace
~~~

## 43. Why custom identifier disagreement blocks

An application-owned identifier such as customer_number can represent strong
contradictory identity evidence.

Stable V1 therefore blocks automatic duplicate classification when the same
namespace carries different values.

## 44. Warning conflicts do not subtract points

This is a key V1 nuance.

DedupScorePolicy does not reduce score for WARNING conflicts.

They remain visible in provenance.

A candidate may therefore have:

~~~text
score = 100
warning conflicts present
decision = duplicate
~~~

if no blocking conflict exists.

## 45. Blocking conflict overrides score threshold

If any conflict is BLOCKING:

~~~text
decision = conflict
~~~

even when score is 100.

The score remains visible and is not reset.

## 46. Address disagreement is not a built-in conflict

StandardConflictDetector does not create an ADDRESS conflict merely because two
addresses differ.

Address is positive evidence when equal.

Stable V1 does not classify address inequality as warning or blocking evidence.

## 47. DedupDecision

Stable values:

~~~text
no_match
review
duplicate
conflict
~~~

## 48. NO_MATCH

Positive evidence does not reach review_threshold, unless a blocking conflict
forces conflict instead.

## 49. REVIEW

The score reaches review_threshold but not duplicate_threshold.

This is visible evidence for human or application review.

It is not an automatic duplicate.

## 50. DUPLICATE

The score reaches duplicate_threshold and there is no blocking conflict.

This remains an assessment only.

No merge occurs.

## 51. CONFLICT

At least one blocking conflict exists.

The candidate remains reviewable, but automatic duplicate selection is blocked.

## 52. CandidateAssessment

One result contains:

~~~text
candidate
provenance
~~~

Convenience properties expose:

~~~text
score
decision
~~~

## 53. DeduplicationEngine.evaluate

For one incoming row, the engine:

~~~text
build incoming DedupProfile
        |
        v
retrieve CandidateRecord values
        |
        v
for each candidate:
  match signals
  detect conflicts
  score evidence
  build provenance
        |
        v
sort assessments
~~~

## 54. Deterministic ordering

Assessments sort by:

~~~text
score DESC
candidate.entity_id ASC
~~~

Decision is not a separate ordering key.

Equal-score candidates are ordered lexically by entity_id.

## 55. CandidateSource iteration order is not final ordering

The engine sorts after assessment.

Applications should not rely on the source iteration order for review ranking.

## 56. DedupProvenance

Every CandidateAssessment retains:

~~~text
candidate_entity_id
score
decision
matches
conflicts
~~~

This is the stable evidence record for one candidate.

## 57. summary()

DedupProvenance.summary returns a compact deterministic explanation.

Shape:

~~~text
dedup decision=<decision> score=<score> signals=<sorted signal names>
~~~

If no signals matched:

~~~text
signals=none
~~~

## 58. as_dict()

DedupProvenance.as_dict exposes machine-readable evidence.

For each match:

~~~text
signal
key
value
~~~

For each conflict:

~~~text
signal
severity
key
incoming_values
candidate_values
~~~

## 59. Provenance contains potentially sensitive values

Unlike privacy-minimized DomainEvents, dedup provenance intentionally contains
the evidence used to justify a decision.

That may include:

~~~text
email
phone
full name
organization
address
external ID
custom identifier
~~~

Applications should treat provenance as potentially sensitive operational data.

## 60. Provenance storage requires policy

If provenance is persisted or displayed, define:

~~~text
authorization
retention
redaction
encryption-at-rest policy
audit access
deletion lifecycle
~~~

Avoid sending full provenance to broad logs or telemetry by default.

## 61. DeduplicationEngine.detect

The same engine implements ImportDeduplicator.

detect calls evaluate and then keeps only assessments whose decision is exactly:

~~~text
duplicate
~~~

## 62. Conservative exactly-one rule

Automatic DuplicateResult.match is returned only when:

~~~text
number of DUPLICATE assessments == 1
~~~

All other cases return DuplicateResult.no_match.

## 63. Zero duplicate candidates

If all candidates are:

~~~text
no_match
review
conflict
~~~

detect returns no match.

## 64. Exactly one duplicate candidate

The engine returns:

~~~text
DuplicateResult.match
existing_entity_id = candidate ID
reason = provenance.summary()
~~~

## 65. Multiple duplicate candidates

If two or more candidates reach DUPLICATE:

~~~text
detect -> no_match
~~~

The engine refuses to auto-select one candidate.

This remains true even though evaluate has a deterministic sort order.

## 66. REVIEW is not auto-selected

A single review-level candidate remains:

~~~text
detect -> no_match
~~~

Applications that need review evidence should use evaluate.

## 67. CONFLICT is not auto-selected

A conflict candidate is never returned as the automatic duplicate.

Its evidence remains available through evaluate.

## 68. detect() loses ambiguity detail by design

DuplicateResult is a simple ImportDeduplicator bridge.

When detect returns no match, that can mean:

~~~text
no strong candidate
one or more review candidates
one or more conflicts
multiple duplicate candidates
~~~

Use evaluate when those distinctions matter.

## 69. ImportPipeline integration

DeduplicationEngine can be passed directly:

~~~python
pipeline = ImportPipeline(
    reader=reader,
    deduplicator=engine,
    persister=persister,
)
~~~

No wrapper adapter is needed.

## 70. Import behavior for unique duplicate

When exactly one duplicate is found:

~~~text
duplicates   += 1
rows_skipped += 1
persister is not called
~~~

Detailed ImportRowResult retains duplicate_entity_id.

## 71. Import behavior for ambiguous duplicate set

When multiple candidates are DUPLICATE, detect returns no match.

ImportPipeline therefore proceeds to persistence unless the application adds a
separate review gate.

This is a deliberate boundary of the simple ImportDeduplicator contract.

## 72. Review workflow should call evaluate

For review-oriented applications:

~~~python
assessments = engine.evaluate(row)
~~~

Then inspect:

~~~text
candidate ID
score
decision
matches
conflicts
provenance
~~~

before deciding what happens next.

## 73. CandidateSource can pre-filter for scale

A custom source can use indexed evidence before returning candidates:

~~~text
incoming row
   |
   v
extract lookup keys
   |
   v
database/search query
   |
   v
small candidate set
   |
   v
DeduplicationEngine.evaluate
~~~

Candidate generation remains an extension point.

## 74. No built-in repository-backed Contact candidate source

Stable V1 provides:

~~~text
CandidateSource protocol
InMemoryCandidateSource
~~~

It does not hard-code ContactRepository lookup strategy.

Applications choose scalable retrieval behavior.

## 75. Candidate recall depends on CandidateSource

If the true duplicate is never returned by CandidateSource, the engine cannot
score it.

Matching quality and candidate retrieval quality are separate concerns.

## 76. No fuzzy similarity

Full-name or address near-matches receive no partial credit.

This is conservative and deterministic by design.

## 77. Score is not probability

A score of 70 does not mean a 70 percent chance of duplication.

The score is a rules-based weighted total.

It should not be presented as a calibrated probability.

## 78. ExternalIdentity vs deduplication

ExternalIdentity answers:

~~~text
Does this external-system record key already map to a CRM entity?
~~~

Deduplication answers:

~~~text
Does this incoming record share enough normalized evidence with a candidate?
~~~

An exact ExternalIdentity is one high-confidence dedup signal, but the concepts
remain separate.

## 79. Exact external identity default behavior

One matching external identity contributes 100.

Without blocking conflict:

~~~text
decision = duplicate
~~~

## 80. Custom identifier default behavior

One matching custom identifier contributes 100.

A contradictory value in the same namespace is BLOCKING.

This gives application-owned stable identifiers strong positive and negative
identity semantics.

## 81. Warning conflict example

Incoming:

~~~text
email = ada@example.com
full name = Ada Lovelace
organization = Analytical Engines
phone = +33611111111
~~~

Candidate:

~~~text
email = ada@example.com
full name = Ada Lovelace
organization = Analytical Engines
phone = +33622222222
~~~

Positive score:

~~~text
70 + 25 + 15
= 110
-> 100 after cap
~~~

Phone disagreement is WARNING.

Default final decision remains DUPLICATE.

The warning remains in provenance.

## 82. Blocking conflict example

Incoming:

~~~text
email = ada@example.com
full name = Ada Lovelace
organization = Analytical Engines
customer_number = C-001
~~~

Candidate:

~~~text
email = ada@example.com
full name = Ada Lovelace
organization = Analytical Engines
customer_number = C-999
~~~

Positive score reaches 100.

Custom identifier disagreement is BLOCKING.

Final result:

~~~text
score = 100
decision = conflict
~~~

## 83. Multiple matches of one signal

If two email addresses match, provenance can retain two EMAIL SignalMatch values.

The score still contributes the EMAIL weight once.

This separates detailed evidence from scoring policy.


## 84. Custom score policy

Applications can redefine weights and thresholds:

~~~python
policy = DedupScorePolicy(
    weights={
        DedupSignal.EMAIL: 50,
        DedupSignal.PHONE: 50,
        DedupSignal.EXTERNAL_IDENTITY: 100,
    },
    review_threshold=50,
    duplicate_threshold=100,
)
~~~

Signals absent from the mapping contribute zero.

Matching normalization remains unchanged unless a different matcher is injected.

## 85. Engine components are injectable

DeduplicationEngine accepts:

~~~text
source
matcher
conflict_detector
score_policy
~~~

The defaults are:

~~~text
StandardSignalMatcher
StandardConflictDetector
DedupScorePolicy
~~~

This separates candidate retrieval, evidence matching, contradiction detection
and classification policy.

## 86. Complete evaluation example

~~~python
engine = DeduplicationEngine(
    InMemoryCandidateSource(
        (
            CandidateRecord(
                "contact-1",
                {
                    "email": "ada@example.com",
                    "full_name": "Ada Lovelace",
                    "organization": "Analytical Engines",
                },
            ),
            CandidateRecord(
                "contact-2",
                {
                    "email": "grace@example.com",
                    "full_name": "Grace Hopper",
                },
            ),
        )
    )
)

row = ImportRow(
    1,
    {
        "email": "ADA@EXAMPLE.COM",
        "display_name": "ada lovelace",
        "company": "analytical engines",
    },
)

assessments = engine.evaluate(row)

assert assessments[0].candidate.entity_id == "contact-1"
assert assessments[0].score == 100
assert assessments[0].decision is DedupDecision.DUPLICATE
~~~

## 87. Import bridge example

~~~python
result = engine.detect(row)

assert result.is_duplicate is True
assert result.existing_entity_id == "contact-1"
~~~

The result is automatic only because exactly one candidate is DUPLICATE.

## 88. Ambiguous duplicate example

~~~python
record = {
    "email": "ada@example.com",
    "full_name": "Ada Lovelace",
    "organization": "Analytical Engines",
}

engine = DeduplicationEngine(
    InMemoryCandidateSource(
        (
            CandidateRecord(
                "contact-1",
                record,
            ),
            CandidateRecord(
                "contact-2",
                record,
            ),
        )
    )
)

result = engine.detect(
    ImportRow(
        1,
        record,
    )
)

assert result.is_duplicate is False
~~~

The engine refuses hidden candidate selection.

## 89. Review example

A single email match gives:

~~~text
score = 70
decision = review
detect = no match
~~~

The application can route the CandidateAssessment to a secured review UI.

## 90. Deterministic ranking example

Suppose assessments produce:

~~~text
contact-b score 70
contact-c score 100
contact-a score 100
~~~

The final evaluate order is:

~~~text
contact-a 100
contact-c 100
contact-b 70
~~~

because score descends and entity_id breaks ties.

## 91. Provenance machine-readable example

~~~python
evidence = assessment.provenance.as_dict()
~~~

The result contains:

~~~text
candidate_entity_id
score
decision
matches[]
conflicts[]
~~~

This is useful for review, secured audit evidence and explicit merge
justification.

## 92. Provenance and Contact Merge

MergeService accepts optional DedupProvenance.

That lets a reviewed dedup decision travel into merge audit evidence.

Chapter 20 will show that exact transaction boundary.

## 93. Deduplication after import normalization

ImportPipeline places deduplication after:

~~~text
map
normalize
validate
~~~

The engine still normalizes its own supported signals again when building
DedupProfile.

This is boundary defense rather than an assumption that import rows are always
perfectly normalized.

## 94. Dedup normalization can raise

Email, phone and external identity normalization reuse strict domain functions.

If invalid signal data reaches DedupProfile, candidate evaluation may raise.

In ImportPipeline, deduplicator failures propagate.

Validate predictable source-quality problems before deduplication when you want
row-level reporting instead.

## 95. Candidate construction can raise

CandidateRecord builds its DedupProfile during construction.

Invalid candidate evidence can therefore fail before evaluate is called.

Candidate-source data quality is an application responsibility.

## 96. Detection is deterministic

Given the same:

~~~text
incoming mapping
candidate records
matcher
conflict detector
score policy
~~~

the engine produces the same normalized evidence, score, decision and
assessment ordering.

Stable V1 matching contains no randomness.

## 97. Explainability rule

Every default score can be reconstructed from:

~~~text
matched unique signal types
configured weights
100-point cap
review threshold
duplicate threshold
blocking conflicts
~~~

No hidden model contributes to the result.

## 98. CandidateRecord IDs are generic strings

CandidateRecord does not require ContactId.

This keeps the engine reusable for candidate sources that project other
application identifiers.

Applications can parse IDs into typed CRM IDs at their own boundary.

## 99. CandidateSource structural typing

A custom CandidateSource can be:

~~~text
repository-backed
search-index-backed
tenant-aware
organization-scoped
batch-aware
~~~

as long as it yields CandidateRecord values for one ImportRow.

## 100. A repository-backed source pattern

Conceptually:

~~~text
incoming row
   |
   +--> normalized email
   +--> normalized phone
   +--> external identity
   |
   v
query indexed Contact candidates
   |
   v
project to CandidateRecord
   |
   v
DeduplicationEngine.evaluate
~~~

The candidate source should narrow the set without changing scoring semantics.

## 101. Deduplication and privacy

The engine can normalize and retain personally identifying values as evidence.

Do not assume the privacy rules of DomainEvent payloads apply to
DedupProvenance.

The two models serve different purposes.

## 102. Import integration example

~~~python
persister = RecordingPersister()

pipeline = ImportPipeline(
    reader=IterableReader(
        (
            {
                "email": "ADA@EXAMPLE.COM",
                "full_name": "Ada Lovelace",
                "organization": "Analytical Engines",
            },
            {
                "email": "grace@example.com",
                "full_name": "Grace Hopper",
                "organization": "US Navy",
            },
        )
    ),
    deduplicator=engine,
    persister=persister,
)

report = pipeline.run()
~~~

If Ada has exactly one DUPLICATE assessment:

~~~text
Ada
-> skipped as duplicate
-> persister not called

Grace
-> no automatic duplicate
-> persisted
~~~

## 103. Import report evidence

The generic ImportReport retains:

~~~text
duplicates count
rows_skipped count
duplicate_entity_id
~~~

It does not retain the complete DedupProvenance.

Applications needing full review evidence should call evaluate and store
provenance through an explicit secured path.

## 104. ExternalIdentity can be used before fuzzy-style review

A useful application architecture is:

~~~text
incoming record
   |
   v
deterministic ExternalIdentity lookup
   |
   +--> found -> route existing owner
   |
   +--> not found
           |
           v
       candidate retrieval
           |
           v
       DeduplicationEngine
~~~

Stable V1 still uses exact normalized matching, but this separation keeps strong
identity routing distinct from evidence-based review.

## 105. Why exact matching is a sound V1 baseline

A conservative rules engine offers:

~~~text
determinism
explainability
portable behavior
easy testing
no model dependency
no probabilistic opacity
~~~

Applications can build more advanced CandidateSource or matching policies later
without changing the stable import and merge boundaries.

## Common mistakes

### Treating score as probability

The score is a deterministic rules score, not a calibrated likelihood.

### Expecting fuzzy name matching

Stable V1 uses exact normalized equality.

### Expecting CandidateSource to scan the CRM automatically

The source determines which candidates are evaluated.

### Loading every Contact into InMemoryCandidateSource in production

Use a pre-filtering CandidateSource suitable for your scale.

### Counting multiple emails as multiple weights

Scoring counts unique signal types.

### Assuming warning conflicts subtract score

They do not. Warning conflicts remain provenance.

### Assuming score 100 always means duplicate

A blocking conflict forces decision conflict while score can remain 100.

### Treating address disagreement as a built-in conflict

StandardConflictDetector does not generate address conflicts.

### Lowercasing external IDs

External-ID case remains provider-owned.

### Lowercasing custom identifier values

Namespaces normalize, but identifier values preserve case after trim and NFKC.

### Assuming evaluate preserves CandidateSource order

Assessments sort by score descending then entity_id ascending.

### Assuming detect selects the first duplicate

detect returns a match only when exactly one DUPLICATE candidate exists.

### Treating ambiguous no-match as no evidence

Use evaluate. detect deliberately collapses ambiguity into no automatic match.

### Expecting REVIEW to skip an import row

Only one unambiguous DUPLICATE becomes DuplicateResult.match.

### Automatically merging after detection

Detection and merge are separate explicit operations.

### Logging provenance without privacy review

Provenance can contain emails, phone numbers, addresses and identifiers.

### Sending invalid signals directly into deduplication

Strict domain normalizers can raise during candidate evaluation.

## Testing deduplication

Signal extraction tests should cover:

~~~text
email aliases
phone aliases
full-name fallback
organization aliases
structured address
external identity
custom identifiers
case and whitespace rules
~~~

Matcher tests should cover:

~~~text
all seven signals
multiple values
exact normalized equality
namespaced matches
~~~

Scoring tests should cover:

~~~text
default weights
unique signal type scoring
100 cap
review threshold
duplicate threshold
custom thresholds
custom weights
invalid thresholds
negative weights
~~~

Conflict tests should cover:

~~~text
email warning
phone warning
full-name warning
organization warning
external identity warning
custom identifier blocking
blocking override
~~~

Engine tests should cover:

~~~text
deterministic ordering
unique duplicate
review-only candidate
conflict candidate
ambiguous duplicate candidates
provenance summary
provenance as_dict
~~~

Import integration tests should cover:

~~~text
unique duplicate skipped
persister not called for duplicate
duplicate_entity_id retained
ambiguous set not auto-selected
~~~

## What you learned

You can now explain and use:

- CandidateRecord;
- CandidateSource;
- InMemoryCandidateSource;
- CandidateAssessment;
- DedupProfile;
- DedupSignal;
- normalize_text;
- all seven stable signal types;
- field alias precedence;
- StandardSignalMatcher;
- exact normalized equality;
- SignalMatch;
- DEFAULT_SIGNAL_WEIGHTS;
- DedupScorePolicy;
- unique-signal scoring;
- score capping;
- configurable thresholds;
- DedupDecision;
- ConflictSeverity;
- DedupConflict;
- StandardConflictDetector;
- warning conflicts;
- blocking custom identifier conflicts;
- blocking conflict override;
- deterministic assessment ordering;
- DedupProvenance;
- provenance summary and as_dict;
- provenance privacy boundaries;
- DeduplicationEngine.evaluate;
- DeduplicationEngine.detect;
- the exactly-one-duplicate rule;
- ImportDeduplicator integration;
- the distinction between ExternalIdentity, dedup evidence and merge.

## LEVEL 5 in progress

The Data Operations path now contains:

~~~text
17 External Identities
18 Importing Data
19 Deduplication
~~~

PyCRMKit can now identify and explain likely duplicate candidates.

It still does not mutate or merge them.

## Next

The next chapter is **20 - Contact Merge**.

The flow becomes:

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
        +--> profile reconciliation
        +--> relationships
        +--> activities
        +--> tags
        +--> custom fields
        +--> external identities
        +--> duplicate archive
        +--> audit
        |
        v
MergeResult
~~~

The next learning question is:

> How does PyCRMKit merge two Contacts conservatively, transactionally and
> audibly without silently choosing a primary record or losing related data?
