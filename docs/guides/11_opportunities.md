# Opportunities

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter continues **LEVEL 3 - Sales**.

Chapter 10 introduced the Lead as a commercial qualification process. An
Opportunity begins when the CRM needs to represent a concrete potential business
outcome: something with a name, a customer context, an optional estimated value,
an expected close date, ownership, and eventually a Pipeline/Stage.

The central question becomes:

~~~text
What business outcome are we pursuing?
~~~

## What you will build

You will create Opportunities, attach them to Contacts and Organizations,
represent money safely with Decimal, model probability and expected-close data,
close Opportunities through explicit lifecycle operations, query them through
portable repository semantics, and understand the boundary between Opportunity
state and Pipeline movement.

By the end of the chapter:

~~~text
Lead
"Should we pursue this?"
        |
        v
Opportunity
"What commercial outcome are we pursuing?"
        |
        v
Pipeline / Stage
"Where is it in the sales process?"
~~~

Pipeline policy itself is the subject of chapter 12.

## 1. Why Opportunity exists

A Lead and an Opportunity are deliberately different aggregates.

~~~text
Lead
= qualification of commercial interest

Opportunity
= potential commercial transaction or business outcome
~~~

An Opportunity can carry concepts that do not belong on a Lead:

~~~text
name
estimated value
currency
probability
expected close date
owner
pipeline
stage
commercial outcome
~~~

## 2. The stable Opportunity model

The V1 Opportunity aggregate contains:

~~~text
id
name
contact_id
organization_id
pipeline_id
stage_id
stage_entered_at
estimated_value
currency
probability
expected_close_date
owner_id
status
created_at
updated_at
~~~

Identity uses the strongly typed OpportunityId.

## 3. Opportunity requires a name

name is required.

~~~python
from pycrmkit import CRM

crm = CRM.memory()

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
)

assert opportunity.name == "Enterprise renewal"
~~~

Names are normalized with Unicode NFKC, trimming and whitespace collapse.

~~~python
opportunity = crm.opportunities.create(
    name="  Enterprise   renewal ",
    contact_id=contact.id,
)

assert opportunity.name == "Enterprise renewal"
~~~

A blank name raises:

~~~text
ValidationError
code = opportunity.name.required
~~~

The stable maximum length is 300 characters.

## 4. A Contact is required

Every Opportunity requires a typed ContactId.

~~~text
Opportunity
    |
    v
ContactId
~~~

PyCRMKit does not copy Contact profile data into the Opportunity.

The Contact remains the customer-identity aggregate.

## 5. Organization is optional

An Opportunity may also belong to an Organization context:

~~~python
organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    organization_id=organization.id,
)

assert opportunity.organization_id == organization.id
~~~

This supports both individual and account-oriented selling.

## 6. Opportunity identity is typed

OpportunityId is distinct from ContactId, OrganizationId and LeadId.

Conceptually:

~~~text
OpportunityId != ContactId
OpportunityId != OrganizationId
OpportunityId != LeadId
~~~

UUID-backed storage does not erase domain meaning.

## 7. Opportunity lifecycle

OpportunityStatus is independent from Pipeline stages.

The stable lifecycle is:

~~~text
           +----> WON
           |
OPEN ------+----> LOST
           |
           +----> CANCELLED
~~~

WON, LOST and CANCELLED are terminal.

There is no reopen operation in the V1 Opportunity aggregate.

## 8. New Opportunities start OPEN

~~~python
from pycrmkit.opportunities import OpportunityStatus

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
)

assert opportunity.status is OpportunityStatus.OPEN
assert opportunity.is_terminal is False
~~~

The facade does not accept an arbitrary initial status.

## 9. Money is optional

An Opportunity may exist before financial estimation.

~~~python
opportunity = crm.opportunities.create(
    name="Discovery opportunity",
    contact_id=contact.id,
)

assert opportunity.estimated_value is None
assert opportunity.currency is None
assert opportunity.money is None
~~~

This supports early sales processes where value is still unknown.

## 10. Amount and currency form one semantic pair

If estimated_value is supplied, currency is required.

If currency is supplied, estimated_value is required.

Valid:

~~~python
from decimal import Decimal

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    estimated_value=Decimal("25000.00"),
    currency="EUR",
)
~~~

Invalid:

~~~text
estimated_value without currency
-> ValidationError
   opportunity.currency.required

currency without estimated_value
-> ValidationError
   opportunity.estimated_value.required
~~~

The pair is normalized through the shared Money primitive.

## 11. Decimal is mandatory for money

PyCRMKit deliberately rejects float for monetary values.

Correct:

~~~python
Decimal("25000.00")
~~~

Not correct:

~~~python
25000.00
~~~

A float amount raises:

~~~text
ValidationError
code = money.amount.decimal_required
~~~

This prevents binary floating-point semantics from becoming part of the
financial domain contract.

## 12. Money must be finite

Money rejects non-finite Decimal values.

Examples:

~~~text
NaN
Infinity
-Infinity
~~~

raise:

~~~text
ValidationError
code = money.amount.non_finite
~~~

The Money primitive does not impose a positivity rule; the V1 contract is about
Decimal precision, finiteness and explicit currency.

## 13. Currency normalization

Currency is structurally validated as exactly three ASCII letters and normalized
to uppercase.

~~~python
opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    estimated_value=Decimal("25000.00"),
    currency=" eur ",
)

assert opportunity.currency == "EUR"
~~~

Invalid structural currency codes raise:

~~~text
ValidationError
code = money.currency.invalid
~~~

PyCRMKit does not bundle a complete ISO currency registry in this primitive.

## 14. The money property

Opportunity exposes a convenient read property:

~~~python
money = opportunity.money

assert money is not None
assert money.amount == Decimal("25000.00")
assert money.currency == "EUR"
~~~

If no estimated value exists:

~~~text
opportunity.money -> None
~~~

The persisted Opportunity still stores estimated_value and currency explicitly.

## 15. Probability is optional

probability models the current commercial likelihood as a Decimal in the closed
interval:

~~~text
0 <= probability <= 1
~~~

Examples:

~~~python
Decimal("0")
Decimal("0.25")
Decimal("0.65")
Decimal("1")
~~~

A missing probability is also valid.

## 16. Probability must be Decimal

Correct:

~~~python
probability=Decimal("0.65")
~~~

A float is rejected:

~~~text
probability=0.65
        |
        v
ValidationError
code = opportunity.probability.decimal_required
~~~

## 17. Probability range

Values outside [0, 1] are rejected.

Examples:

~~~text
Decimal("-0.01")
Decimal("1.01")
Decimal("NaN")
~~~

raise:

~~~text
ValidationError
code = opportunity.probability.out_of_range
~~~

## 18. Expected close date

expected_close_date is an optional date.

~~~python
from datetime import date

opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    expected_close_date=date(2026, 12, 31),
)
~~~

The contract expects exactly a date value.

A datetime is rejected with:

~~~text
ValidationError
code = opportunity.expected_close_date.invalid
~~~

## 19. Owner

owner_id is an optional normalized text identifier.

~~~python
opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    owner_id="  seller-42 ",
)

assert opportunity.owner_id == "seller-42"
~~~

The maximum length is 255 characters.

PyCRMKit does not impose an IAM model on owner_id; integrations decide how that
identifier maps to users, teams or another ownership system.

## 20. Pipeline and Stage references

Opportunity can store:

~~~text
pipeline_id
stage_id
stage_entered_at
~~~

These fields connect the aggregate to Pipeline policy without making Pipeline a
property bag inside Opportunity.

A Stage requires a Pipeline:

~~~text
stage_id != None
and
pipeline_id == None
        |
        v
ValidationError
code = opportunity.stage_id.pipeline_required
~~~

## 21. Pipeline/Stage creation references are not existence validation

An important V1 boundary:

~~~python
opportunity = crm.opportunities.create(
    name="Enterprise renewal",
    contact_id=contact.id,
    pipeline_id="sales",
    stage_id="proposal",
)
~~~

Creation stores normalized opaque identifiers.

The create operation does not load PipelineRepository to prove that the Pipeline
or Stage exists.

Actual movement uses persisted Pipeline policy and is covered in chapter 12.

## 22. Stage entry time

When an Opportunity is created with a stage and no explicit stage_entered_at,
the aggregate uses created_at.

Conceptually:

~~~text
stage_id present
stage_entered_at omitted
        |
        v
stage_entered_at = created_at
~~~

The public facade does not currently expose stage_entered_at as a create
parameter; this behavior is therefore automatic for normal facade use.

## 23. Stage-entry chronology

If an Opportunity aggregate is reconstructed with stage_entered_at, it must
satisfy:

~~~text
created_at <= stage_entered_at <= updated_at
~~~

Violations raise:

~~~text
opportunity.stage_entered_at.before_creation
opportunity.stage_entered_at.after_update
~~~

A stage-entry timestamp without stage_id is also invalid:

~~~text
ValidationError
code = opportunity.stage_entered_at.stage_required
~~~

## 24. Stage duration

Opportunity exposes:

~~~python
duration = opportunity.stage_duration(at)
~~~

When stage_entered_at exists, it returns the elapsed timedelta.

If there is no stage:

~~~text
stage_duration(...) -> None
~~~

An endpoint before stage entry raises:

~~~text
ValidationError
code = opportunity.stage.duration.invalid
~~~

This gives higher layers a stable primitive for stage-aging analytics.

## 25. High-level facade surface

The stable V1 Opportunities facade exposes:

~~~text
crm.opportunities.create(...)
crm.opportunities.move(...)
~~~

It does **not** expose:

~~~text
crm.opportunities.get(...)
crm.opportunities.list(...)
crm.opportunities.mark_won(...)
crm.opportunities.mark_lost(...)
crm.opportunities.cancel(...)
~~~

Those lifecycle/query operations exist on OpportunityService.

As with Leads, the guide follows the actual frozen V1 API.

## 26. Why move is special

crm.opportunities.move() is not a free-form status update.

It loads the persisted Pipeline, resolves an allowed transition, applies the
target Stage's default probability, updates stage_entered_at and may close the
Opportunity when the target Stage is terminal.

Conceptually:

~~~text
Opportunity
    |
    v
Pipeline definition
    |
    v
Transition policy
    |
    v
Target Stage
    |
    +--> default probability
    |
    +--> optional terminal outcome
~~~

The detailed rules belong to chapter 12.

## 27. OpportunityService

The exported framework-agnostic service provides:

~~~text
create
get
move
mark_won
mark_lost
cancel
list
~~~

Example import:

~~~python
from pycrmkit.opportunities import OpportunityService
~~~

move requires PipelineRepository when stage movement is requested.

The other lifecycle operations can work with OpportunityRepository alone.

## 28. Mark an Opportunity won

Using OpportunityService:

~~~python
opportunity = service.mark_won(opportunity.id)

assert opportunity.status is OpportunityStatus.WON
assert opportunity.is_terminal is True
~~~

Only OPEN Opportunities can be closed.

## 29. Mark an Opportunity lost

~~~python
opportunity = service.mark_lost(opportunity.id)

assert opportunity.status is OpportunityStatus.LOST
assert opportunity.is_terminal is True
~~~

## 30. Cancel an Opportunity

~~~python
opportunity = service.cancel(opportunity.id)

assert opportunity.status is OpportunityStatus.CANCELLED
assert opportunity.is_terminal is True
~~~

CANCELLED is a commercial lifecycle outcome distinct from LOST.

## 31. Terminal-state protection

After an Opportunity leaves OPEN, another direct outcome is invalid.

Example:

~~~text
OPEN -> WON
WON  -> LOST
        |
        v
InvalidStateError
code = opportunity.transition.invalid
~~~

The error context exposes:

~~~text
from
to
~~~

## 32. Outcome timestamps

Direct outcome transitions must satisfy:

~~~text
transition_at >= created_at
~~~

An earlier timestamp raises:

~~~text
ValidationError
code = opportunity.transition.before_creation
~~~

Successful transitions update updated_at.

## 33. Pipeline movement is blocked after closure

move_to_stage() rejects any non-OPEN Opportunity.

~~~text
WON / LOST / CANCELLED
        |
        v
stage movement rejected
~~~

The domain error is:

~~~text
InvalidStateError
code = opportunity.stage.transition.closed
~~~

This prevents a closed commercial outcome from silently continuing through the
sales pipeline.

## 34. Query Opportunities

OpportunityService.list() accepts OpportunityQuery.

Portable filters are:

~~~text
status
contact_id
organization_id
pipeline_id
stage_id
owner_id
currency
expected_close_date
~~~

Example:

~~~python
from pycrmkit.opportunities import OpportunityQuery

page = service.list(
    OpportunityQuery(
        status="open",
        currency="eur",
        owner_id="SELLER-42",
    )
)
~~~

## 35. Query normalization

OpportunityQuery normalizes:

~~~text
pipeline_id -> whitespace-normalized + case-folded
stage_id    -> whitespace-normalized + case-folded
owner_id    -> whitespace-normalized + case-folded
currency    -> trimmed + uppercase
~~~

This allows qualified adapters to preserve consistent query semantics.

Stored presentation values may retain their normalized case; matching is
case-insensitive for pipeline/stage/owner in the Memory adapter.

## 36. Query by Contact and Organization

~~~python
page = service.list(
    OpportunityQuery(
        contact_id=contact_id,
        organization_id=organization_id,
    )
)
~~~

This provides customer/account sales views without copying customer data into
Opportunity.

## 37. Query by expected close date

expected_close_date filtering is exact in V1:

~~~python
page = service.list(
    OpportunityQuery(
        expected_close_date=date(2026, 12, 31),
    )
)
~~~

The contract does not define a date range in OpportunityQuery.

Applications needing forecasting windows can compose higher-level read models or
future query capabilities rather than assuming unsupported repository semantics.

## 38. Pagination

OpportunityService.list() accepts OffsetPageRequest:

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = service.list(
    OpportunityQuery(status="open"),
    OffsetPageRequest(
        limit=25,
        offset=0,
    ),
)

print(page.items)
print(page.total)
print(page.has_next)
print(page.has_previous)
~~~

Totals are exact under the repository contract.

## 39. Deterministic ordering

OpportunityRepository lists with:

~~~text
created_at DESC
id ASC
~~~

Newest Opportunities appear first.

ID stabilizes equal creation timestamps so offset pagination remains
deterministic.

## 40. get vs find

Repository semantics distinguish:

~~~text
get(OpportunityId)
-> Opportunity
-> raises NotFoundError when missing

find(OpportunityId)
-> Opportunity | None
~~~

Missing get uses:

~~~text
NotFoundError
code = opportunity.not_found
~~~

OpportunityService exposes get().

## 41. Repository contract

Adapter authors implement:

~~~text
get(OpportunityId) -> Opportunity
find(OpportunityId) -> Opportunity | None
save(Opportunity) -> None
list(
    OpportunityQuery,
    OffsetPageRequest,
) -> Page[Opportunity]
~~~

Adapters must preserve:

~~~text
name
typed customer references
pipeline/stage references
stage_entered_at
Decimal estimated value
currency
Decimal probability
expected close date
owner
status
timestamps
~~~

Repository writes do not commit an outer Unit of Work.

## 42. Memory adapter copy isolation

MemoryOpportunityRepository deep-copies state on save and read.

Therefore:

~~~text
load Opportunity
mutate returned object
do not call save
        |
        v
persisted state does not change
~~~

The Memory adapter is a contract-faithful lightweight persistence implementation,
not a permissive fake.

## 43. Facade creation is transactional

crm.opportunities.create() runs inside a Unit of Work:

~~~text
open UoW
   |
   v
OpportunityService.create
   |
   v
repository.save
   |
   v
record event/audit
   |
   v
commit
~~~

The facade records:

~~~text
opportunity.created
~~~

with normal actor/correlation context.

## 44. Movement events

When crm.opportunities.move() succeeds, the facade records:

~~~text
opportunity.stage_changed
~~~

If movement changes the commercial status through a terminal Stage, it also
records one of:

~~~text
opportunity.won
opportunity.lost
opportunity.cancelled
~~~

These events are part of the facade orchestration, not direct
OpportunityService side effects.

## 45. Opportunity events are not Timeline entries by default

The stable Timeline projector documented in chapter 09 supports selected
Activity, Task and Communication events.

Do not assume Opportunity events appear in Timeline merely because they are
Domain Events.

Sales state and customer-history projection remain separate abstractions.

## 46. Complete facade example

~~~python
from datetime import UTC, date, datetime
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.opportunities import OpportunityStatus

clock = FixedClock(
    datetime(2026, 9, 27, 17, 0, tzinfo=UTC)
)

crm = CRM.memory(clock=clock).with_context(
    actor_id="sales-user-42",
    correlation_id="opportunity-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

opportunity = crm.opportunities.create(
    name="  Enterprise   renewal ",
    contact_id=contact.id,
    organization_id=organization.id,
    estimated_value=Decimal("25000.00"),
    currency=" eur ",
    probability=Decimal("0.65"),
    expected_close_date=date(2026, 12, 31),
    owner_id=" seller-42 ",
)

assert opportunity.name == "Enterprise renewal"
assert opportunity.status is OpportunityStatus.OPEN
assert opportunity.money is not None
assert opportunity.money.amount == Decimal("25000.00")
assert opportunity.money.currency == "EUR"
assert opportunity.probability == Decimal("0.65")
assert opportunity.owner_id == "seller-42"
~~~

No Pipeline is required merely to create and value an Opportunity.

## 47. Complete service/query example

~~~python
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.opportunities import (
    OpportunityQuery,
    OpportunityService,
    OpportunityStatus,
)
from pycrmkit.storage.memory import MemoryOpportunityRepository

clock = FixedClock(
    datetime(2026, 9, 27, 18, 0, tzinfo=UTC)
)
ids = UUID4Factory()
repository = MemoryOpportunityRepository()
service = OpportunityService(
    repository,
    id_factory=ids,
    clock=clock,
)

contact_id = ids.new(ContactId)

opportunity = service.create(
    name="Enterprise expansion",
    contact_id=contact_id,
    estimated_value=Decimal("40000"),
    currency="EUR",
    probability=Decimal("0.40"),
    expected_close_date=date(2027, 1, 31),
    owner_id="Seller-42",
)

page = service.list(
    OpportunityQuery(
        status=OpportunityStatus.OPEN,
        contact_id=contact_id,
        currency="eur",
        owner_id="seller-42",
        expected_close_date=date(2027, 1, 31),
    ),
    OffsetPageRequest(
        limit=10,
        offset=0,
    ),
)

assert page.items == (opportunity,)
assert page.total == 1

clock.advance(timedelta(hours=1))

won = service.mark_won(opportunity.id)

assert won.status is OpportunityStatus.WON
assert won.is_terminal is True
~~~

## 48. Validation examples

Missing currency:

~~~python
from pycrmkit.exceptions import ValidationError

try:
    service.create(
        name="Invalid value",
        contact_id=contact_id,
        estimated_value=Decimal("1000"),
    )
except ValidationError as exc:
    assert exc.code == "opportunity.currency.required"
~~~

Float probability:

~~~python
try:
    service.create(
        name="Invalid probability",
        contact_id=contact_id,
        probability=0.5,
    )
except ValidationError as exc:
    assert exc.code == "opportunity.probability.decimal_required"
~~~

Stage without Pipeline:

~~~python
try:
    service.create(
        name="Invalid stage",
        contact_id=contact_id,
        stage_id="proposal",
    )
except ValidationError as exc:
    assert exc.code == "opportunity.stage_id.pipeline_required"
~~~

## 49. Opportunity vs Lead

Keep the boundary explicit:

~~~text
Lead
qualification process

Opportunity
commercial outcome being pursued
~~~

Lead conversion can create an Opportunity atomically, but Opportunity is a
first-class aggregate and can also be created independently through its public
facade.

The atomic Lead Conversion workflow is chapter 13.

## 50. Opportunity vs Pipeline

Opportunity owns:

~~~text
commercial identity
value
probability
customer references
expected close date
owner
commercial outcome status
current pipeline/stage references
current stage-entry timestamp
~~~

Pipeline owns:

~~~text
ordered Stage definitions
allowed transitions
initial Stage
terminal Stage semantics
default probabilities
transition policy
~~~

This boundary becomes central in chapter 12.

## Common mistakes

### Treating Lead and Opportunity as synonyms

Lead qualifies interest. Opportunity represents the potential commercial
outcome.

### Using float for money

estimated_value requires Decimal.

### Providing amount without currency

The pair must be complete.

### Assuming currency accepts arbitrary strings

Money requires exactly three ASCII letters.

### Using float for probability

Probability also requires Decimal.

### Expressing probability as 65 instead of 0.65

The stable range is 0 through 1.

### Passing datetime as expected_close_date

The V1 field requires date.

### Creating a Stage without pipeline_id

stage_id requires pipeline_id.

### Assuming create validates Pipeline/Stage existence

Creation stores opaque normalized references. Actual transition policy is
enforced during movement.

### Calling crm.opportunities.get or list

Those methods are not on the stable V1 facade. Use OpportunityService/repository
when you need that lower-level surface.

### Calling crm.opportunities.mark_won directly

The facade does not expose that method. Direct outcome operations are available
on OpportunityService; facade-level terminal outcomes normally result from
Pipeline movement.

### Moving a closed Opportunity

Only OPEN Opportunities may move through Pipeline stages.

### Querying persistence technology directly

Use OpportunityQuery so qualified adapters preserve the same observable
semantics.

## Testing Opportunity workflows

A facade-level value test can remain simple:

~~~python
from decimal import Decimal

from pycrmkit import CRM
from pycrmkit.opportunities import OpportunityStatus

def test_opportunity_can_be_created_with_value() -> None:
    crm = CRM.memory()
    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )

    opportunity = crm.opportunities.create(
        name="Enterprise renewal",
        contact_id=contact.id,
        estimated_value=Decimal("25000"),
        currency="EUR",
        probability=Decimal("0.6"),
    )

    assert opportunity.status is OpportunityStatus.OPEN
    assert opportunity.money is not None
    assert opportunity.money.amount == Decimal("25000")
~~~

Service/repository tests can separately prove terminal lifecycle, portable
queries, copy isolation and adapter conformance.

## What you learned

You can now explain and use:

- Opportunity and OpportunityId;
- Opportunity vs Lead;
- required name and ContactId;
- optional OrganizationId;
- OpportunityStatus;
- OPEN / WON / LOST / CANCELLED lifecycle;
- terminal-state protection;
- Decimal-safe Money;
- estimated_value + currency pairing;
- three-letter currency normalization;
- optional Decimal probability;
- [0, 1] probability semantics;
- expected_close_date;
- owner_id;
- pipeline_id / stage_id boundary;
- automatic stage_entered_at initialization;
- stage chronology and stage_duration();
- facade vs OpportunityService;
- direct service-level won/lost/cancel operations;
- OpportunityQuery filters;
- exact expected-close-date filtering;
- deterministic created_at DESC / id ASC ordering;
- exact pagination;
- get vs find semantics;
- MemoryOpportunityRepository copy isolation;
- opportunity.created;
- stage/outcome events from facade movement;
- Opportunity vs Pipeline responsibility boundaries.

## Next

The next chapter is **12 - Pipelines**.

Opportunities answer:

~~~text
What commercial outcome are we pursuing?
~~~

Pipelines answer:

~~~text
Through which ordered sales process does that Opportunity move,
which transitions are allowed,
and which stages close the outcome?
~~~

Chapter 12 will introduce Pipeline, Stage, transition policy, initial and terminal
Stages, default probabilities, stage movement and stage-duration semantics.
