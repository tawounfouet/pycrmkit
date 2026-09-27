# Leads

> Applies to PyCRMKit 1.0.x. Baseline: 1.0.0.

This chapter opens **LEVEL 3 - Sales**.

The CRM core tells you who the customer is. Activities and Tasks tell you what
happened and what should happen next. A Lead introduces a different question:

~~~text
Is this commercial interest worth pursuing?
~~~

A Lead is therefore not a Contact, not an Opportunity, and not a generic status
field attached to a person. It is a dedicated commercial qualification
aggregate with its own lifecycle.

## What you will build

You will create Contacts and Organizations, capture Leads, qualify or disqualify
them, inspect the complete Lead lifecycle, query Leads through the portable
service/repository contract, and understand where Lead-to-Opportunity conversion
begins.

By the end of the chapter, this mental model should be clear:

~~~text
Contact / Organization
        |
        v
       Lead
        |
        +----> disqualified
        |
        v
    qualified
        |
        v
 Opportunity
~~~

Conversion itself is deliberately deferred to chapter 13.

## 1. Why Lead exists

A Contact represents a person.

An Organization represents a company or other organization.

A Lead represents a **commercial interest associated with a Contact**, optionally
in the context of an Organization.

That distinction matters.

~~~text
Contact
= customer identity

Lead
= commercial qualification process

Opportunity
= concrete potential business outcome
~~~

The same Contact can exist even when no sales process is active.

## 2. The stable Lead model

The V1 Lead aggregate contains:

~~~text
id
contact_id
organization_id
source
status
created_at
updated_at

converted_opportunity_id
conversion_idempotency_key
conversion_request_fingerprint
~~~

The last three fields belong to the conversion workflow and will be covered in
chapter 13. Normal Lead creation leaves them empty.

## 3. Lead identity is typed

A Lead uses LeadId.

Its required customer link uses ContactId.

Its optional organization link uses OrganizationId.

This prevents accidental cross-domain ID substitution.

Conceptually:

~~~text
LeadId           != ContactId
ContactId        != OrganizationId
OrganizationId   != OpportunityId
~~~

Even though all may be UUID-backed, their domain meaning remains explicit.

## 4. A Lead requires a Contact

The minimum facade workflow begins with a Contact:

~~~python
from pycrmkit import CRM

crm = CRM.memory()

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

lead = crm.leads.create(
    contact_id=contact.id,
)

assert lead.contact_id == contact.id
~~~

Lead creation requires a typed ContactId.

The Lead domain does not duplicate the Contact profile. It stores the identity
reference.

## 5. Organization is optional

A Lead can also be linked to an Organization:

~~~python
organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

lead = crm.leads.create(
    contact_id=contact.id,
    organization_id=organization.id,
)

assert lead.organization_id == organization.id
~~~

This supports both:

~~~text
person-only commercial interest

and

person + account/company commercial interest
~~~

## 6. Acquisition source

source records where the Lead came from.

Examples:

~~~text
website
partner referral
trade show
outbound
legacy crm
campaign
manual
~~~

Example:

~~~python
lead = crm.leads.create(
    contact_id=contact.id,
    source="  partner   referral ",
)

assert lead.source == "partner referral"
~~~

The Lead aggregate:

- applies Unicode NFKC normalization;
- trims outer whitespace;
- collapses repeated whitespace;
- converts blank text to None;
- limits source to 120 characters.

A source longer than 120 characters raises:

~~~text
ValidationError
code = lead.source.too_long
~~~

## 7. Lead lifecycle

The stable V1 lifecycle is:

~~~text
NEW
 |
 +---- open ----------> OPEN
 |                       |
 |                       +---- contacted ----+
 |                       |                   |
 +---- contacted ----------------------------> CONTACTED
 |                                           |
 +---- qualify ------------------------------+
 |                       |                   |
 |                       +---- qualify ------> QUALIFIED
 |                                           |
 +---- disqualify ---------------------------+
                         |                   |
                         +---- disqualify ----+
                                             |
CONTACTED -----------------------------------+
   |
   +---- qualify --------> QUALIFIED
   |
   +---- disqualify -----> DISQUALIFIED

QUALIFIED
   |
   +---- disqualify -----> DISQUALIFIED
   |
   +---- convert --------> CONVERTED

DISQUALIFIED   terminal
CONVERTED      terminal
~~~

More compactly:

| From | Allowed targets |
| --- | --- |
| NEW | OPEN, CONTACTED, QUALIFIED, DISQUALIFIED |
| OPEN | CONTACTED, QUALIFIED, DISQUALIFIED |
| CONTACTED | QUALIFIED, DISQUALIFIED |
| QUALIFIED | DISQUALIFIED, CONVERTED |
| DISQUALIFIED | none |
| CONVERTED | none |

## 8. New Leads start NEW

Facade creation always creates the Lead in NEW:

~~~python
from pycrmkit.leads import LeadStatus

lead = crm.leads.create(
    contact_id=contact.id,
)

assert lead.status is LeadStatus.NEW
~~~

The caller does not choose an arbitrary initial lifecycle state.

## 9. Qualify a Lead

A Lead may be qualified from:

~~~text
NEW
OPEN
CONTACTED
~~~

The high-level facade exposes:

~~~python
lead = crm.leads.qualify(lead.id)

assert lead.status is LeadStatus.QUALIFIED
~~~

Qualification means the commercial interest has crossed the application's
qualification threshold.

PyCRMKit intentionally does not define your business qualification scoring
rules. Your application decides **when** to call qualify; PyCRMKit guarantees the
state transition semantics once it does.

## 10. Disqualify a Lead

A Lead may be disqualified from:

~~~text
NEW
OPEN
CONTACTED
QUALIFIED
~~~

Example:

~~~python
lead = crm.leads.disqualify(lead.id)

assert lead.status is LeadStatus.DISQUALIFIED
~~~

DISQUALIFIED is terminal in the V1 lifecycle.

There is no reopen transition.

## 11. Terminal-state protection

After a Lead becomes DISQUALIFIED, another qualification attempt is rejected:

~~~python
from pycrmkit.exceptions import InvalidStateError

try:
    crm.leads.qualify(lead.id)
except InvalidStateError as exc:
    assert exc.code == "lead.transition.invalid"
~~~

The same error code protects all invalid lifecycle transitions:

~~~text
InvalidStateError
code = lead.transition.invalid
~~~

The error context includes:

~~~text
lead_id
from_status
to_status
~~~

## 12. Transition timestamps

Every lifecycle transition receives a timestamp from the configured Clock.

The transition must satisfy:

~~~text
transition_at >= created_at
~~~

An earlier transition is rejected with:

~~~text
ValidationError
code = lead.transition.invalid_timestamp
~~~

Successful transitions update updated_at.

This keeps lifecycle chronology consistent and deterministic under FixedClock
tests.

## 13. High-level facade surface

The stable V1 Leads facade exposes:

~~~text
crm.leads.create(...)
crm.leads.qualify(...)
crm.leads.disqualify(...)
crm.leads.convert(...)
~~~

A subtle but important point:

~~~text
crm.leads.open(...)          does not exist
crm.leads.mark_contacted(...) does not exist
crm.leads.get(...)           does not exist
crm.leads.list(...)          does not exist
~~~

Those operations exist at the exported LeadService/repository layer.

The guide documents the contract as implemented rather than pretending the
facade has a larger surface.

## 14. LeadService exposes the complete qualification lifecycle

LeadService is a public domain service:

~~~python
from pycrmkit.leads import LeadService
~~~

Its V1 operations are:

~~~text
create
get
open
mark_contacted
qualify
disqualify
list
~~~

Conversion is intentionally implemented by a separate LeadConversionService.

## 15. OPEN with LeadService

A newly created Lead may move to OPEN:

~~~python
from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.leads import LeadService, LeadStatus
from pycrmkit.storage.memory import MemoryLeadRepository

ids = UUID4Factory()
repository = MemoryLeadRepository()
service = LeadService(repository)

lead = service.create(
    contact_id=ids.new(ContactId),
    source="website",
)

lead = service.open(lead.id)

assert lead.status is LeadStatus.OPEN
~~~

OPEN means the captured commercial interest has entered active handling.

## 16. CONTACTED with LeadService

From NEW or OPEN:

~~~python
lead = service.mark_contacted(lead.id)

assert lead.status is LeadStatus.CONTACTED
~~~

CONTACTED records that a commercial interaction has occurred at the Lead
qualification level.

The actual call, meeting, email or message should still be represented by the
appropriate Activity/Communication domain when relationship history matters.

## 17. Lead lifecycle is not Activity history

Do not overload LeadStatus to represent every interaction.

Wrong mental model:

~~~text
lead.status = "called"
lead.status = "emailed"
lead.status = "meeting"
~~~

Preferred:

~~~text
LeadStatus
= commercial qualification state

Activity / Communication
= what actually happened
~~~

This separation keeps sales state and customer history composable.

## 18. Direct qualification is valid

The lifecycle intentionally allows:

~~~text
NEW -> QUALIFIED
~~~

A Lead does not have to pass through OPEN and CONTACTED first.

This supports cases such as:

~~~text
high-quality inbound referral
already-qualified imported Lead
manual qualification based on known context
~~~

Similarly:

~~~text
NEW -> DISQUALIFIED
~~~

is valid when the commercial interest can be rejected immediately.

## 19. QUALIFIED does not mean converted

QUALIFIED and CONVERTED are distinct:

~~~text
QUALIFIED
= ready for opportunity conversion

CONVERTED
= conversion has actually produced/linked the Opportunity
~~~

Do not mark a Lead CONVERTED manually in application workflows.

Use the conversion service/facade so the Lead and Opportunity remain
transactionally coherent.

That workflow is covered in chapter 13.

## 20. Conversion provenance fields are protected

The aggregate contains:

~~~text
converted_opportunity_id
conversion_idempotency_key
conversion_request_fingerprint
~~~

Those fields must remain coherent.

Conversion provenance on a non-CONVERTED Lead is rejected.

Partial provenance on a converted Lead is also rejected.

These invariants prevent persistence adapters from reconstructing impossible
conversion state.

## 21. Query Leads with LeadQuery

LeadService.list() accepts LeadQuery.

Portable filters are:

~~~text
status
contact_id
organization_id
source
~~~

Example:

~~~python
from pycrmkit.leads import LeadQuery, LeadStatus

page = service.list(
    LeadQuery(
        status=LeadStatus.CONTACTED,
        source="website",
    )
)
~~~

Adapters implement the same query semantics.

## 22. Query by Contact

~~~python
page = service.list(
    LeadQuery(
        contact_id=contact_id,
    )
)
~~~

This asks:

~~~text
Which Leads belong to this Contact?
~~~

It does not query Contact fields such as email or name. Those belong to the
Contact domain.

## 23. Query by Organization

~~~python
page = service.list(
    LeadQuery(
        organization_id=organization_id,
    )
)
~~~

This supports account-oriented sales views without embedding Organization state
inside Lead.

## 24. Source query normalization

LeadQuery normalizes source differently from stored presentation text.

Query input is:

- whitespace-normalized;
- case-folded.

Therefore:

~~~text
"  Partner   Referral "
"partner referral"
"PARTNER REFERRAL"
~~~

match the same stored Lead source under the qualified adapters.

The stored Lead source retains its normalized presentation case.

## 25. Query filters combine

LeadQuery filters are conjunctive.

Conceptually:

~~~text
status == contacted
AND contact_id == ...
AND organization_id == ...
AND source == website
~~~

Only Leads satisfying all supplied filters are returned.

## 26. Pagination

LeadService.list() accepts OffsetPageRequest:

~~~python
from pycrmkit.core.pagination import OffsetPageRequest

page = service.list(
    LeadQuery(
        status=LeadStatus.CONTACTED,
    ),
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

The repository contract returns exact pagination metadata.

## 27. Deterministic ordering

LeadRepository uses:

~~~text
created_at DESC
id ASC
~~~

So the newest Leads appear first.

ID stabilizes ties when multiple Leads share the same creation timestamp.

Deterministic ordering is required for repeatable offset pagination.

## 28. get vs find

The repository contract distinguishes:

~~~text
get(LeadId)
-> Lead
-> raises NotFoundError when missing

find(LeadId)
-> Lead | None
~~~

LeadService exposes get().

Nullable lookup remains a repository-level capability.

Missing get uses:

~~~text
NotFoundError
code = lead.not_found
~~~

## 29. Repository contract

Adapter authors implement:

~~~text
get(LeadId) -> Lead
find(LeadId) -> Lead | None
save(Lead) -> None
list(LeadQuery, OffsetPageRequest) -> Page[Lead]
~~~

The contract requires:

~~~text
typed Lead state fidelity
NotFound behavior
exact pagination
created_at DESC / id ASC ordering
status/contact/organization/source filters
no implicit outer commit
adapter-independent domain entities
~~~

## 30. Memory adapter copy isolation

MemoryLeadRepository is not a permissive mock.

It deep-copies stored and returned Leads.

This protects persistence semantics such as:

~~~text
load Lead
mutate returned object
do not call save
        |
        v
stored repository state must remain unchanged
~~~

The behavior mirrors the explicit-save boundary expected from production
adapters.

## 31. Facade operations are transactional

High-level facade operations use a Unit of Work.

For create:

~~~text
open Unit of Work
      |
      v
LeadService.create
      |
      v
save Lead
      |
      v
record event/audit
      |
      v
commit
~~~

Qualification and disqualification follow the same transactional pattern.

## 32. Lead facade events

The V1 facade records these events for the Lead operations in this chapter:

~~~text
lead.created
lead.qualified
lead.disqualified
~~~

The facade records context such as actor/correlation through the common CRM
runtime.

LeadService used directly is a lower-level domain service; it does not itself
perform the facade's event/audit orchestration.

## 33. Why facade and service are separate

The layers serve different purposes:

~~~text
CRM facade
= transaction + context + event/audit orchestration + developer DX

LeadService
= framework-agnostic Lead domain operations

LeadRepository
= persistence contract
~~~

That separation preserves PyCRMKit's domain-first architecture.

## 34. Complete facade example

~~~python
from datetime import UTC, datetime, timedelta

from pycrmkit import CRM
from pycrmkit.core.time import FixedClock
from pycrmkit.leads import LeadStatus

clock = FixedClock(
    datetime(2026, 9, 27, 14, 0, tzinfo=UTC)
)

crm = CRM.memory(clock=clock).with_context(
    actor_id="sales-user-42",
    correlation_id="lead-guide-001",
)

contact = crm.contacts.create(
    display_name="Ada Lovelace",
)

organization = crm.organizations.create(
    legal_name="Analytical Engines Ltd",
)

lead = crm.leads.create(
    contact_id=contact.id,
    organization_id=organization.id,
    source="  partner   referral ",
)

assert lead.status is LeadStatus.NEW
assert lead.source == "partner referral"

clock.advance(timedelta(minutes=15))

lead = crm.leads.qualify(lead.id)

assert lead.status is LeadStatus.QUALIFIED
assert lead.updated_at == clock.now()
~~~

At this point the Lead is ready for the future conversion chapter.

## 35. Complete service/query example

~~~python
from datetime import UTC, datetime, timedelta

from pycrmkit.contacts import ContactId
from pycrmkit.core.ids import UUID4Factory
from pycrmkit.core.pagination import OffsetPageRequest
from pycrmkit.core.time import FixedClock
from pycrmkit.leads import LeadQuery, LeadService, LeadStatus
from pycrmkit.storage.memory import MemoryLeadRepository

clock = FixedClock(
    datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
)
ids = UUID4Factory()
repository = MemoryLeadRepository()

service = LeadService(
    repository,
    id_factory=ids,
    clock=clock,
)

contact_id = ids.new(ContactId)

lead = service.create(
    contact_id=contact_id,
    source="  Partner   Referral ",
)

clock.advance(timedelta(minutes=5))
lead = service.open(lead.id)

clock.advance(timedelta(minutes=5))
lead = service.mark_contacted(lead.id)

page = service.list(
    LeadQuery(
        status=LeadStatus.CONTACTED,
        contact_id=contact_id,
        source="partner referral",
    ),
    OffsetPageRequest(
        limit=10,
        offset=0,
    ),
)

assert page.items == (lead,)
assert page.total == 1
~~~

## 36. Invalid transition example

~~~python
from pycrmkit.exceptions import InvalidStateError

lead = service.disqualify(lead.id)

try:
    service.qualify(lead.id)
except InvalidStateError as exc:
    assert exc.code == "lead.transition.invalid"
~~~

DISQUALIFIED cannot move back into the active qualification flow.

## 37. Invalid source example

~~~python
from pycrmkit.exceptions import ValidationError

try:
    service.create(
        contact_id=contact_id,
        source="x" * 121,
    )
except ValidationError as exc:
    assert exc.code == "lead.source.too_long"
~~~

Domain validation remains independent of persistence technology.

## 38. Lead vs Opportunity

A useful boundary is:

~~~text
Lead
"Should we pursue this?"

Opportunity
"What commercial outcome are we pursuing?"
~~~

Lead contains no sales pipeline stage, estimated value, currency, probability or
expected close date.

Those concepts belong to Opportunity/Pipeline.

## 39. Lead vs Task

Another important distinction:

~~~text
Lead
= commercial qualification state

Task
= actionable work to perform
~~~

A sales application may create Tasks around a Lead, but Lead should not become a
generic to-do list.

## 40. Lead vs Timeline

Lead state is a source domain concept.

Timeline is a read projection of selected customer-history events.

The V1 Timeline chapter focused on Activity, Task and Communication projection.
Do not assume every Lead transition automatically appears in Timeline merely
because it emits a Domain Event.

## Common mistakes

### Treating Contact and Lead as the same thing

Contact is customer identity. Lead is commercial qualification state.

### Creating a Lead without a typed ContactId

The Lead contract requires ContactId.

### Copying Contact fields into Lead

Keep customer identity in Contact and reference it by ID.

### Assuming Organization is required

organization_id is optional.

### Treating source as an unrestricted blob

source is normalized and limited to 120 characters.

### Assuming every Lead must pass NEW -> OPEN -> CONTACTED -> QUALIFIED

Direct NEW -> QUALIFIED is valid.

### Trying to reopen DISQUALIFIED

DISQUALIFIED is terminal in V1.

### Calling crm.leads.open or crm.leads.list

Those methods are not on the stable V1 facade. Use the exported LeadService and
repository contract when that lower-level surface is appropriate.

### Manually setting CONVERTED

Use the conversion workflow so Lead and Opportunity remain coherent.

### Treating LeadStatus as interaction history

Calls, meetings and messages belong to Activity/Communication.

### Querying ORM models directly

Use LeadQuery so all qualified adapters preserve the same semantics.

### Assuming repository save commits the transaction

Repository writes do not commit an outer Unit of Work.

## Testing Lead workflows

Facade-level tests should prove public lifecycle behavior:

~~~python
from pycrmkit import CRM
from pycrmkit.exceptions import InvalidStateError
from pycrmkit.leads import LeadStatus

def test_lead_can_be_qualified_then_disqualified() -> None:
    crm = CRM.memory()

    contact = crm.contacts.create(
        display_name="Ada Lovelace",
    )

    lead = crm.leads.create(
        contact_id=contact.id,
        source="website",
    )

    lead = crm.leads.qualify(lead.id)
    assert lead.status is LeadStatus.QUALIFIED

    lead = crm.leads.disqualify(lead.id)
    assert lead.status is LeadStatus.DISQUALIFIED

    try:
        crm.leads.qualify(lead.id)
    except InvalidStateError as exc:
        assert exc.code == "lead.transition.invalid"
~~~

Service/repository tests can separately prove OPEN/CONTACTED transitions,
portable queries, copy isolation and adapter conformance.

## What you learned

You can now explain and use:

- Lead and LeadId;
- Lead vs Contact vs Organization;
- required ContactId;
- optional OrganizationId;
- source normalization and length rules;
- LeadStatus;
- the six-state Lead lifecycle;
- direct NEW -> QUALIFIED;
- explicit OPEN and CONTACTED service transitions;
- terminal DISQUALIFIED and CONVERTED states;
- InvalidStateError for invalid transitions;
- transition timestamp chronology;
- facade vs LeadService boundaries;
- LeadQuery;
- status/contact/organization/source filters;
- source query normalization;
- deterministic created_at DESC / id ASC ordering;
- exact pagination;
- get vs find semantics;
- MemoryLeadRepository copy isolation;
- transactional facade behavior;
- lead.created / lead.qualified / lead.disqualified events;
- the conversion boundary without yet implementing the conversion workflow.

## Next

The next chapter is **11 - Opportunities**.

Leads answer:

~~~text
Should we pursue this commercial interest?
~~~

Opportunities answer:

~~~text
What concrete business outcome are we pursuing,
for what value, and in what state?
~~~

Chapter 11 introduces the Opportunity aggregate before chapter 12 adds Pipelines
and chapter 13 joins everything through atomic Lead Conversion.
