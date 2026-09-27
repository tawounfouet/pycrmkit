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

