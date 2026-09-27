# Lead Conversion

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter closes **LEVEL 3 - Sales**.

The three previous chapters introduced the pieces independently:

~~~text
Lead
= should we pursue this commercial interest?

Opportunity
= what potential business outcome are we pursuing?

Pipeline
= through which governed sales process does it move?
~~~

Lead Conversion is the workflow that joins them.

The central question becomes:

~~~text
How do we turn one qualified Lead into exactly one Opportunity,
atomically and safely under retry?
~~~

## What you will build

You will qualify a Lead, convert it into an Opportunity, inherit Contact and
Organization references, optionally initialize the Opportunity in a Pipeline,
use deterministic idempotency, understand request fingerprints, prove rollback
semantics, observe conversion events and audit, and safely retry after a
post-commit subscriber failure.

By the end of the chapter:

~~~text
Qualified Lead
      |
      v
LeadConversionService
      |
      +--> optional Pipeline initial Stage
      |
      +--> create Opportunity
      |
      +--> mark Lead converted
      |
      v
single Unit of Work
      |
      +--> opportunity.created
      +--> lead.converted
      |
      v
commit once
~~~

## 1. Why conversion is a workflow

Lead Conversion changes more than one aggregate.

It must:

~~~text
read Lead
validate Lead state
optionally read Pipeline
create Opportunity
change Lead state
persist both
record cross-aggregate provenance
commit consistently
~~~

This is not merely:

~~~python
lead.status = "converted"
~~~

and it is not merely:

~~~python
crm.opportunities.create(...)
~~~

It is a cross-aggregate application workflow with explicit transaction and
idempotency requirements.

## 2. Public API

The stable V1 façade exposes conversion through:

~~~text
crm.leads.convert(...)
~~~

Signature conceptually:

~~~text
lead_id
name?
estimated_value?
currency?
pipeline_id?
expected_close_date?
owner_id?
idempotency_key?
~~~

The façade returns the resulting Opportunity.

## 3. A Lead must be qualified first

Conversion accepts only:

~~~text
LeadStatus.QUALIFIED
~~~

Typical flow:

~~~python
lead = crm.leads.create(
    contact_id=contact.id,
)

lead = crm.leads.qualify(
    lead.id,
)

opportunity = crm.leads.convert(
    lead.id,
)
~~~

Trying to convert NEW, OPEN, CONTACTED or DISQUALIFIED raises:

~~~text
InvalidStateError
code = lead.conversion.requires_qualified
~~~

The error context includes the Lead ID and current status.

## 4. Conversion is terminal for the Lead

Successful conversion changes:

~~~text
QUALIFIED -> CONVERTED
~~~

CONVERTED is terminal in the Lead lifecycle.

The Lead records:

~~~text
converted_opportunity_id
conversion_idempotency_key
conversion_request_fingerprint
~~~

Those fields form conversion provenance.

## 5. Conversion creates an Opportunity

A first successful request creates one Opportunity.

~~~python
from decimal import Decimal

opportunity = crm.leads.convert(
    lead.id,
    name="Enterprise rollout",
    estimated_value=Decimal("25000"),
    currency="EUR",
)
~~~

The Opportunity is persisted before the Lead is marked converted inside the same
outer Unit of Work.

## 6. Customer identity is inherited

The resulting Opportunity inherits the Lead customer references.

~~~text
Lead.contact_id
    |
    v
Opportunity.contact_id

Lead.organization_id
    |
    v
Opportunity.organization_id
~~~

The caller does not provide alternate Contact/Organization IDs to convert().

Example:

~~~python
assert opportunity.contact_id == lead.contact_id
assert (
    opportunity.organization_id
    == lead.organization_id
)
~~~

This preserves the commercial lineage.

## 7. Opportunity name

name is optional on conversion.

When supplied, it is Unicode-normalized, trimmed and whitespace-collapsed before
Opportunity creation.

~~~python
opportunity = crm.leads.convert(
    lead.id,
    name="  Enterprise   rollout ",
)

assert opportunity.name == "Enterprise rollout"
~~~

## 8. Default Opportunity name

If name is omitted, PyCRMKit derives:

~~~text
Lead {lead_id}
~~~

Conceptually:

~~~python
opportunity = crm.leads.convert(
    lead.id,
)

assert opportunity.name == f"Lead {lead.id}"
~~~

This gives conversion a deterministic name without requiring presentation data
from Contact.

## 9. Blank explicit names remain invalid

If a caller explicitly provides blank/whitespace name, normalization produces an
empty string and normal Opportunity validation rejects it.

The resulting error is:

~~~text
ValidationError
code = opportunity.name.required
~~~

Omitting name and explicitly passing an empty name are therefore different.

## 10. Value and currency use Opportunity rules

Conversion forwards:

~~~text
estimated_value
currency
~~~

into Opportunity creation.

Therefore all chapter 11 Money rules still apply:

~~~text
Decimal amount
finite amount
amount + currency supplied together
three-letter currency structure
currency normalized uppercase
~~~

Example:

~~~python
opportunity = crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000.00"),
    currency=" eur ",
)

assert opportunity.estimated_value == Decimal("25000.00")
assert opportunity.currency == "EUR"
~~~

## 11. Expected close date and owner

Conversion can initialize:

~~~text
expected_close_date
owner_id
~~~

Example:

~~~python
from datetime import date

opportunity = crm.leads.convert(
    lead.id,
    expected_close_date=date(2027, 1, 31),
    owner_id=" seller-42 ",
)

assert opportunity.expected_close_date == date(2027, 1, 31)
assert opportunity.owner_id == "seller-42"
~~~

Opportunity validation and normalization remain authoritative.

## 12. Conversion without a Pipeline

pipeline_id is optional.

Without a Pipeline:

~~~text
Opportunity.pipeline_id = None
Opportunity.stage_id = None
Opportunity.probability = None
~~~

unless other Opportunity fields were explicitly provided.

The conversion workflow does not require Pipeline participation.

## 13. Conversion with a Pipeline

When pipeline_id is supplied, conversion loads the persisted Pipeline.

~~~python
opportunity = crm.leads.convert(
    lead.id,
    pipeline_id="sales",
)
~~~

The workflow derives:

~~~text
pipeline_id
initial stage_id
initial Stage default_probability
~~~

from the persisted definition.

## 14. Pipeline ID normalization

Pipeline lookup uses PipelineRepository semantics.

A request such as:

~~~text
" SALES "
~~~

resolves to the normalized Pipeline:

~~~text
sales
~~~

The resulting Opportunity stores the normalized Pipeline ID.

## 15. Initial Stage is automatic

Suppose:

~~~text
sales
├── new        position 0
├── qualified  position 10
└── proposal   position 20
~~~

Conversion with pipeline_id="sales" initializes:

~~~text
Opportunity.pipeline_id = "sales"
Opportunity.stage_id    = "new"
~~~

The caller does not choose an arbitrary conversion Stage.

## 16. Initial default probability is automatic

If the initial Stage defines:

~~~text
new.default_probability = Decimal("0.10")
~~~

conversion creates:

~~~text
Opportunity.probability = Decimal("0.10")
~~~

This differs from ordinary crm.opportunities.create(), which stores Pipeline /
Stage references without loading Pipeline policy.

That distinction is important:

~~~text
Opportunity.create
+ pipeline/stage references
-> no automatic Stage probability lookup

Lead conversion
+ pipeline_id
-> load Pipeline
-> initial Stage
-> initial default probability
~~~

## 17. Pipeline repository requirement at service level

LeadConversionService accepts an optional PipelineRepository dependency.

If a lower-level caller requests pipeline_id while no Pipeline repository was
provided, conversion raises:

~~~text
InvalidStateError
code = lead.conversion.pipeline.repository_required
~~~

The normal crm.leads.convert() façade provides the Unit of Work Pipeline
repository automatically.

## 18. Missing Pipeline

If pipeline_id refers to no persisted Pipeline, the repository raises normal
Pipeline not-found semantics:

~~~text
NotFoundError
code = pipeline.not_found
~~~

No Opportunity should be committed by the façade workflow.

## 19. Terminal initial Stage

A Pipeline can technically have a terminal initial Stage.

If conversion initializes into such a Stage, LeadConversionService immediately
applies its outcome to the new Opportunity.

Conceptually:

~~~text
initial Stage terminal WON
        |
        v
create Opportunity at that Stage
        |
        v
mark Opportunity WON
~~~

The same applies to LOST and CANCELLED.

This preserves Stage terminal semantics even during conversion initialization.

## 20. LeadConversionResult

The lower-level service returns:

~~~python
LeadConversionResult
~~~

with:

~~~text
lead
opportunity
created
~~~

For the first successful conversion:

~~~text
created = True
~~~

For a valid idempotent replay:

~~~text
created = False
~~~

The public façade returns only the Opportunity.

## 21. LeadConversionService

The exported cross-aggregate service is:

~~~python
from pycrmkit.leads import LeadConversionService
~~~

It depends on:

~~~text
LeadRepository
OpportunityRepository
IDFactory
Clock
optional PipelineRepository
~~~

Its purpose is domain/application orchestration, not transaction ownership.

## 22. The service is atomic-ready, not a Unit of Work

This is a critical boundary.

LeadConversionService assumes all supplied repositories participate in the same
outer transaction.

~~~text
LeadConversionService
        |
        +--> LeadRepository
        +--> OpportunityRepository
        +--> PipelineRepository
        |
        v
same outer Unit of Work required
~~~

The service does not call commit.

## 23. The façade owns the transaction

crm.leads.convert() wraps the conversion service inside one shared Unit of Work.

~~~text
open UoW
   |
   v
LeadConversionService.convert
   |
   +--> load Lead
   +--> optional Pipeline
   +--> create Opportunity
   +--> mark Lead CONVERTED
   |
   v
record audit/events
   |
   v
commit once
~~~

That is where the public atomicity guarantee comes from.

## 24. What exactly-once means here

PyCRMKit provides **domain-level exactly-once conversion behavior** for one Lead
under retry.

It means:

~~~text
one Lead
        |
        +--> at most one conversion provenance
        |
        +--> one resulting Opportunity for a matching replay
~~~

It does not claim that arbitrary distributed message delivery is globally
exactly-once.

Outbox, durable transport retry and dead-letter processing are separate eventing
concerns covered later in the roadmap.

## 25. Idempotency key

convert() accepts:

~~~text
idempotency_key
~~~

Example:

~~~python
opportunity = crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000"),
    currency="EUR",
    idempotency_key="lead:123:conversion",
)
~~~

The key is stored on the converted Lead as provenance.

## 26. Idempotency key normalization

An explicit key is:

~~~text
Unicode NFKC normalized
trimmed
case preserved
~~~

It is **not** case-folded.

Therefore these are different keys:

~~~text
convert-001
CONVERT-001
~~~

A blank explicit key raises:

~~~text
ValidationError
code = lead.conversion.idempotency_key.required
~~~

The maximum length is 255 characters.

Overlong keys raise:

~~~text
lead.conversion.idempotency_key.too_long
~~~

## 27. Deterministic key when omitted

idempotency_key is optional.

When omitted, PyCRMKit derives:

~~~text
lead-conversion:{lead_id}
~~~

This means even callers that do not manage their own keys still cannot silently
convert the same Lead twice with different requests.

## 28. Why a key alone is insufficient

Consider:

~~~text
request 1:
key = "convert-001"
value = 25000 EUR

request 2:
key = "convert-001"
value = 50000 EUR
~~~

Returning the original Opportunity without detecting the changed request would
hide a caller bug.

Therefore PyCRMKit stores both:

~~~text
idempotency key
+
request fingerprint
~~~

## 29. Request fingerprint

Conversion computes a canonical SHA-256 fingerprint over the effective request.

The fingerprint covers:

~~~text
lead_id
effective Opportunity name
estimated_value
currency
pipeline_id
expected_close_date
owner_id
~~~

The fingerprint is stored on the converted Lead.

## 30. Canonical Decimal fingerprinting

Decimal tokens are normalized before hashing.

Therefore:

~~~text
Decimal("25000.00")
Decimal("25000.0")
Decimal("25000")
~~~

produce equivalent amount tokens for replay purposes.

This is why semantically equivalent retry amounts are accepted.

## 31. Canonical currency fingerprinting

Currency is:

~~~text
trimmed
uppercased
~~~

for fingerprinting.

Therefore:

~~~text
"eur"
" EUR "
"EUR"
~~~

are equivalent in the conversion request fingerprint.

## 32. Canonical Pipeline fingerprinting

pipeline_id is:

~~~text
trimmed
case-folded
~~~

for fingerprinting.

Therefore:

~~~text
"sales"
" SALES "
~~~

are equivalent replay inputs.

## 33. Canonical owner fingerprinting

owner_id is Unicode-normalized, trimmed and whitespace-collapsed for the
fingerprint.

This mirrors the semantic normalization of the resulting Opportunity owner.

## 34. Expected-close-date fingerprinting

expected_close_date is represented by its ISO date string.

Conceptually:

~~~text
2027-01-31
~~~

The request fingerprint therefore remains deterministic across retries.

## 35. First conversion

First request:

~~~text
Lead = QUALIFIED
key + fingerprint not stored
        |
        v
create Opportunity
        |
        v
mark Lead CONVERTED
        |
        v
store Opportunity ID + key + fingerprint
        |
        v
created = True
~~~

## 36. Same key + equivalent request

A retry with the same key and canonical-equivalent request:

~~~text
Lead = CONVERTED
stored key matches
stored fingerprint matches
        |
        v
load existing Opportunity
        |
        v
created = False
~~~

No second Opportunity is created.

## 37. Public replay returns the same Opportunity

At façade level:

~~~python
first = crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000.00"),
    currency="eur",
    pipeline_id="SALES",
    idempotency_key="convert-001",
)

retry = crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000.0"),
    currency="EUR",
    pipeline_id="sales",
    idempotency_key="convert-001",
)

assert retry.id == first.id
~~~

This is the normal retry path.

## 38. Same key + conflicting request

If the key matches but the fingerprint differs:

~~~text
same key
different canonical request
        |
        v
ConflictError
code = lead.conversion.idempotency_conflict
~~~

Example:

~~~python
crm.leads.convert(
    lead.id,
    estimated_value=Decimal("25000"),
    currency="EUR",
    idempotency_key="convert-001",
)

crm.leads.convert(
    lead.id,
    estimated_value=Decimal("30000"),
    currency="EUR",
    idempotency_key="convert-001",
)
~~~

The second call conflicts instead of silently returning the first result.

## 39. Different key after conversion

If the Lead is already converted and a different idempotency key is supplied:

~~~text
InvalidStateError
code = lead.conversion.already_converted
~~~

The Lead-to-Opportunity association is already final.

## 40. Replay requires complete provenance

A CONVERTED Lead created through older/lower-level aggregate behavior may
theoretically lack the complete replay tuple.

If the Lead is converted but does not have:

~~~text
converted_opportunity_id
conversion_idempotency_key
conversion_request_fingerprint
~~~

LeadConversionService cannot safely replay it.

It raises:

~~~text
InvalidStateError
code = lead.conversion.already_converted
~~~

## 41. Conversion provenance is all-or-nothing

Lead.mark_converted() validates provenance completeness.

Providing only part of:

~~~text
opportunity_id
idempotency_key
request_fingerprint
~~~

raises:

~~~text
ValidationError
code = lead.conversion.provenance.incomplete
~~~

The converted Opportunity ID must also be a typed OpportunityId.

## 42. Provenance belongs only to CONVERTED Leads

Lead reconstruction validates that conversion provenance is not attached to
NEW/OPEN/CONTACTED/QUALIFIED/DISQUALIFIED state.

A mismatch raises:

~~~text
ValidationError
code = lead.conversion.provenance.status_mismatch
~~~

This keeps persisted state internally coherent.

## 43. First-conversion events

A successful first façade conversion records:

~~~text
opportunity.created
lead.converted
~~~

The Opportunity event payload includes the Lead ID.

The Lead event payload includes the resulting Opportunity ID.

## 44. Event order

The façade records events in this order:

~~~text
opportunity.created
lead.converted
~~~

after the conversion service has prepared both aggregate states inside the Unit
of Work.

External subscribers observe committed events through the normal runtime event
machinery.

## 45. Replay does not emit duplicate conversion events

When LeadConversionService returns:

~~~text
created = False
~~~

the façade immediately returns the existing Opportunity.

It does not stage another:

~~~text
opportunity.created
lead.converted
~~~

pair.

Therefore idempotent replay also protects event/audit duplication.

## 46. Audit semantics

First conversion stages audit entries for the two aggregate mutations:

~~~text
opportunity.created
lead.converted
~~~

A successful idempotent replay does not add another conversion pair.

This allows audit history to represent the domain mutation once rather than
every transport retry.

## 47. Actor and correlation context

Conversion uses the same CRM runtime context as other façade operations.

Example:

~~~python
crm = CRM.memory().with_context(
    actor_id="seller-42",
    correlation_id="sales-conversion-001",
)
~~~

The resulting first-conversion events/audit carry that context through the
shared Unit of Work.

## 48. Atomic rollback on validation failure

Suppose Opportunity creation fails because currency is invalid:

~~~python
from pycrmkit.exceptions import ValidationError

try:
    crm.leads.convert(
        lead.id,
        estimated_value=Decimal("10000"),
        currency="EU",
        idempotency_key="bad-currency",
    )
except ValidationError:
    pass
~~~

After failure:

~~~text
Lead remains QUALIFIED
Opportunity count remains unchanged
~~~

The public Memory workflow proves both changes roll back together.

## 49. Why rollback works

The façade opens one Unit of Work before calling LeadConversionService.

If conversion raises before commit:

~~~text
working transaction state discarded
        |
        +--> no converted Lead
        +--> no new Opportunity
        +--> no committed conversion audit/events
~~~

This is the required cross-aggregate atomicity boundary.

## 50. Post-commit subscriber failure is different

External event subscribers run after the domain commit.

Therefore a subscriber may fail **after** Lead and Opportunity are already
committed.

Conceptually:

~~~text
domain commit
    |
    v
event subscriber
    |
    X failure
~~~

That subscriber failure cannot roll back already committed domain state.

## 51. Retry after post-commit failure

This is precisely where conversion idempotency matters.

First call:

~~~text
commit succeeds
subscriber raises RuntimeError
caller sees failure
~~~

The caller cannot safely assume whether the domain committed.

Retrying with the same key/request:

~~~text
load CONVERTED Lead
verify key/fingerprint
return existing Opportunity
created = False
~~~

No duplicate Opportunity is produced.

## 52. Domain exactly-once vs event delivery

PyCRMKit V1 conversion guarantees domain-level idempotent retry.

It does **not** make synchronous external subscriber delivery durable.

~~~text
Domain mutation:
idempotent / replay-safe

External transport delivery:
later Eventing/Webhooks concern
~~~

This distinction prevents overclaiming transaction guarantees across process
boundaries.

## 53. Complete façade example

~~~python
from datetime import UTC, date, datetime
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.leads import LeadStatus
from pycrmkit.pipelines import Stage, StageTransition

clock = FixedClock(
    datetime(2026, 9, 27, 21, 0, tzinfo=UTC)
)

crm = CRM.memory(clock=clock).with_context(
    actor_id="seller-42",
    correlation_id="conversion-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

pipeline = crm.pipelines.define(
    id="sales",
    name="Sales",
    stages=(
        Stage(
            "new",
            "New",
            0,
            Decimal("0.10"),
        ),
        Stage(
            "qualified",
            "Qualified",
            10,
            Decimal("0.35"),
        ),
    ),
    transitions=(
        StageTransition(
            "new",
            "qualified",
        ),
    ),
)

lead = crm.leads.create(
    contact_id=contact.id,
    organization_id=organization.id,
    source="website",
)

lead = crm.leads.qualify(
    lead.id,
)

opportunity = crm.leads.convert(
    lead.id,
    name="  Enterprise   rollout ",
    estimated_value=Decimal("25000.00"),
    currency=" eur ",
    pipeline_id=pipeline.id,
    expected_close_date=date(2027, 1, 31),
    owner_id=" seller-42 ",
    idempotency_key="convert-001",
)

assert opportunity.name == "Enterprise rollout"
assert opportunity.contact_id == contact.id
assert opportunity.organization_id == organization.id
assert opportunity.pipeline_id == "sales"
assert opportunity.stage_id == "new"
assert opportunity.probability == Decimal("0.10")
assert opportunity.currency == "EUR"

with crm._runtime.uow_factory() as uow:
    converted = uow.leads.get(lead.id)

assert converted.status is LeadStatus.CONVERTED
assert converted.converted_opportunity_id == opportunity.id
~~~

## 54. Complete idempotent replay example

~~~python
first = crm.leads.convert(
    lead.id,
    name="Enterprise rollout",
    estimated_value=Decimal("25000.00"),
    currency="eur",
    pipeline_id="sales",
    expected_close_date=date(2027, 1, 31),
    owner_id="seller-42",
    idempotency_key="convert-001",
)

retry = crm.leads.convert(
    lead.id,
    name="Enterprise rollout",
    estimated_value=Decimal("25000.0"),
    currency="EUR",
    pipeline_id=" SALES ",
    expected_close_date=date(2027, 1, 31),
    owner_id=" seller-42 ",
    idempotency_key="convert-001",
)

assert retry.id == first.id
~~~

The amount, currency, Pipeline ID and owner inputs are canonical-equivalent for
fingerprinting.

## 55. Service-level created flag

At lower level:

~~~python
first = conversion.convert(
    lead.id,
    estimated_value=Decimal("25000.00"),
    currency="eur",
    idempotency_key="retry-key",
)

retry = conversion.convert(
    lead.id,
    estimated_value=Decimal("25000.0"),
    currency="EUR",
    idempotency_key="retry-key",
)

assert first.created is True
assert retry.created is False
assert retry.opportunity.id == first.opportunity.id
~~~

This lets application layers distinguish new mutation from replay.

## 56. Default idempotency-key example

~~~python
opportunity = crm.leads.convert(
    lead.id,
)
~~~

Internally the stored key is derived as:

~~~text
lead-conversion:{lead.id}
~~~

A retry of the same effective request can therefore resolve to the original
Opportunity without the caller supplying a key.

## 57. Conflict example

~~~python
from pycrmkit.exceptions import ConflictError

crm.leads.convert(
    lead.id,
    estimated_value=Decimal("10000"),
    currency="EUR",
    idempotency_key="same-key",
)

try:
    crm.leads.convert(
        lead.id,
        estimated_value=Decimal("12000"),
        currency="EUR",
        idempotency_key="same-key",
    )
except ConflictError as exc:
    assert (
        exc.code
        == "lead.conversion.idempotency_conflict"
    )
~~~

This is a semantic retry conflict, not a duplicate Opportunity creation.

## 58. Conversion then normal Pipeline movement

A converted Opportunity initialized in a non-terminal initial Stage continues
through the normal Pipeline API.

~~~python
opportunity = crm.leads.convert(
    lead.id,
    pipeline_id="sales",
    idempotency_key="pipeline-conversion",
)

opportunity = crm.opportunities.move(
    opportunity.id,
    to="qualified",
)
~~~

From that point, chapter 12 Pipeline transition rules apply normally.

## 59. Conversion does not emit stage_changed

Initializing the Opportunity at the Pipeline initial Stage happens as part of
Opportunity creation.

The conversion façade records:

~~~text
opportunity.created
lead.converted
~~~

It does not separately emit:

~~~text
opportunity.stage_changed
~~~

for the initial conversion placement.

Later crm.opportunities.move() calls do emit stage-change events.

## 60. Conversion to a terminal initial Stage and events

If the initial Stage is terminal, LeadConversionService closes the new
Opportunity before returning it.

The conversion façade still records the generic first-conversion pair:

~~~text
opportunity.created
lead.converted
~~~

It does not run the OpportunitiesAPI.move() terminal event path.

Therefore do not assume an additional opportunity.won/lost/cancelled event is
emitted merely because conversion initialized into a terminal Stage.

The stable source supports the final Opportunity status, while the façade
conversion code explicitly records only the two conversion events.

## 61. Public façade boundary after conversion

The converted Lead remains accessible to repository/service layers, while the
stable Leads façade still exposes only:

~~~text
create
qualify
disqualify
convert
~~~

There is no:

~~~text
crm.leads.get
crm.leads.list
~~~

in the frozen V1 façade.

Normal Opportunity progression remains:

~~~text
crm.opportunities.move(...)
~~~

## 62. Lead Conversion as a consistency boundary

The workflow protects four related facts:

~~~text
1. Lead was qualified.
2. Exactly one Opportunity is associated with conversion.
3. Lead records that Opportunity identity.
4. Retry semantics can prove whether a request is equivalent.
~~~

Without all four, conversion would be vulnerable to duplicate commercial
records under uncertain retries.

## Common mistakes

### Converting a NEW Lead

Conversion requires QUALIFIED state.

### Creating an Opportunity manually and then changing the Lead

That bypasses the cross-aggregate conversion contract, provenance and
idempotency behavior.

### Assuming Lead Conversion copies Contact data

It copies typed Contact/Organization references, not profile payloads.

### Providing a custom Stage to convert()

The public conversion API accepts pipeline_id, not stage_id. The persisted
Pipeline initial Stage is selected automatically.

### Assuming conversion behaves like Opportunity.create for probability

With a Pipeline, conversion loads the initial Stage and applies its default
probability.

### Reusing one idempotency key for a different request

That raises lead.conversion.idempotency_conflict.

### Retrying with a new key after success

That raises lead.conversion.already_converted.

### Treating key casing as equivalent

Explicit idempotency keys preserve case.

### Passing an empty explicit key

Blank keys are invalid. Omit the key if deterministic default behavior is
desired.

### Assuming the service commits

LeadConversionService does not own commit. Repositories must participate in one
outer Unit of Work.

### Assuming subscriber failure means rollback

Subscribers run after commit; domain state may already be durable.

### Retrying after transport uncertainty by creating another Opportunity

Retry crm.leads.convert() with the same key and effective request instead.

### Expecting duplicate conversion events on retry

A valid replay returns before new event/audit staging.

### Expecting opportunity.stage_changed during initial conversion placement

Initial Pipeline Stage is part of Opportunity creation, not a move operation.

### Claiming distributed exactly-once delivery

The guarantee is domain-level idempotent conversion, not globally durable
exactly-once transport.

## Testing conversion workflows

A high-value test covers first conversion and replay together:

~~~python
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.events import DomainEvent

def test_conversion_is_idempotent() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )
    lead = crm.leads.create(
        contact_id=contact.id,
    )
    lead = crm.leads.qualify(
        lead.id,
    )

    created_events: list[DomainEvent] = []
    converted_events: list[DomainEvent] = []

    crm.events.subscribe(
        "opportunity.created",
        created_events.append,
    )
    crm.events.subscribe(
        "lead.converted",
        converted_events.append,
    )

    first = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("25000.00"),
        currency="eur",
        idempotency_key="convert-001",
    )

    retry = crm.leads.convert(
        lead.id,
        estimated_value=Decimal("25000.0"),
        currency="EUR",
        idempotency_key="convert-001",
    )

    assert retry.id == first.id
    assert len(created_events) == 1
    assert len(converted_events) == 1
~~~

A second test should prove rollback of both aggregate mutations when Opportunity
validation fails.

A third should prove retry after a simulated post-commit subscriber failure.

## What you learned

You can now explain and use:

- Lead-to-Opportunity conversion;
- QUALIFIED as the required source state;
- CONVERTED as terminal Lead state;
- Contact/Organization reference inheritance;
- optional conversion Opportunity fields;
- deterministic default Opportunity name;
- optional Pipeline initialization;
- automatic initial Stage selection;
- automatic initial default probability;
- terminal initial Stage handling;
- LeadConversionResult;
- LeadConversionService;
- service vs Unit of Work transaction ownership;
- crm.leads.convert();
- domain-level exactly-once conversion semantics;
- explicit and derived idempotency keys;
- key validation and normalization;
- canonical request fingerprinting;
- Decimal/currency/Pipeline/owner replay equivalence;
- first request vs replay created flag;
- idempotency conflict;
- different-key already-converted protection;
- conversion provenance invariants;
- single-UoW rollback;
- opportunity.created + lead.converted event pair;
- no duplicate events/audit on replay;
- post-commit subscriber-failure semantics;
- safe retry after uncertain transport outcome;
- conversion followed by normal Pipeline movement.

## LEVEL 3 complete

You have now built the complete Sales Foundation learning layer:

~~~text
Lead
  |
  v
Qualification
  |
  v
Lead Conversion
  |
  v
Opportunity
  |
  v
Pipeline / Stages
  |
  v
WON / LOST / CANCELLED
~~~

The four chapters fit together as one coherent model:

~~~text
10 Leads
11 Opportunities
12 Pipelines
13 Lead Conversion
~~~

## Next

The next chapter begins **LEVEL 4 - Communication & Automation**:

**14 - Email & Communications**

The Sales layer now knows who the customer is, what commercial outcome is being
pursued and how it progresses.

The next learning problem is:

~~~text
How does the CRM represent and deliver communication
while preserving provider independence,
delivery state,
history,
events and observability?
~~~
