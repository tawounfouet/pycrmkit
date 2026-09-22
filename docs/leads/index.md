# Leads

A `Lead` represents an unqualified or partially qualified commercial interest.
`0.3.0b2` completes the public Lead workflow with atomic, idempotent
Lead-to-Opportunity conversion.

## State model

```text
new
open
contacted
qualified
disqualified
converted
```

Domain transitions are explicit. `disqualified` and `converted` are terminal.
Public conversion accepts only a `qualified` Lead.

## Identity and links

A Lead requires a typed `ContactId` and may reference an `OrganizationId`. It can
also record a normalized acquisition `source`.

```python
lead = crm.leads.create(
    contact_id=contact.id,
    organization_id=organization.id,
    source="website",
)
lead = crm.leads.qualify(lead.id)
```

## Public facade

```python
crm.leads.create(...)
crm.leads.qualify(lead.id)
crm.leads.disqualify(lead.id)
crm.leads.convert(...)
```

`get` and `list` remain domain/service capabilities rather than facade methods in
the `0.3` beta surface.

## Lead conversion

```python
from decimal import Decimal

opportunity = crm.leads.convert(
    lead.id,
    name="Enterprise rollout",
    estimated_value=Decimal("25000"),
    currency="EUR",
    pipeline_id="sales",
    idempotency_key="lead:123:conversion",
)
```

The conversion runs inside one Unit of Work:

```text
load Lead
    ↓
validate qualified / replay state
    ↓
load Pipeline when supplied
    ↓
create Opportunity
    ↓
mark Lead converted
    ↓
stage audit + events
    ↓
commit once
```

The resulting Opportunity inherits the Lead's `contact_id` and
`organization_id`. When a pipeline is supplied, conversion enters its initial
stage and applies that stage's default probability.

## Idempotency

A conversion stores the resulting Opportunity identity together with an
idempotency key and a canonical request fingerprint.

- same Lead + same key + equivalent request → returns the existing Opportunity;
- same Lead + same key + conflicting request → `ConflictError`;
- already-converted Lead + different key → `InvalidStateError`;
- omitted key → PyCRMKit derives a deterministic key from the Lead identity.

An idempotent replay does not create another Opportunity and does not emit a
second conversion event/audit pair.

This is domain-level exactly-once behavior. Durable event delivery, outbox,
retry, and dead-letter handling remain later eventing/webhook concerns.

## Events and audit

Successful first conversion commits both aggregates and can emit:

```text
opportunity.created
lead.converted
```

Audit records are staged in the same Unit of Work and avoid persisting raw
contact or organization payloads.
