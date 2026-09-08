# Leads

A `Lead` represents an unqualified or partially qualified commercial interest. `0.3.0a1` introduces the Lead aggregate, repository/service contracts, the Memory adapter, Unit-of-Work participation, and a deliberately narrow facade surface.

## State model

```text
new
open
contacted
qualified
disqualified
converted
```

Domain transitions are explicit. `disqualified` and `converted` are terminal in the initial model. The aggregate can preserve the full declared state model, but public lead-to-opportunity conversion is not exposed until `0.3.0b2`.

## Identity and links

A Lead requires a typed `ContactId` and may reference an `OrganizationId`. It can also record a normalized acquisition `source`.

```python
lead = crm.leads.create(
    contact_id=contact.id,
    organization_id=organization.id,
    source="website",
)
```

## `0.3.0a1` facade surface

```python
crm.leads.create(...)
crm.leads.qualify(lead.id)
crm.leads.disqualify(lead.id)
```

`crm.leads.convert(...)` is intentionally absent at this milestone. Conversion requires Opportunities and idempotency rules that belong to `0.3.0b2`.

## Events and audit

Facade mutations participate in the same Unit of Work as Lead persistence and audit recording. Successful commits can emit:

```text
lead.created
lead.qualified
lead.disqualified
```

Event payloads and audit changes avoid embedding raw contact or organization data.
