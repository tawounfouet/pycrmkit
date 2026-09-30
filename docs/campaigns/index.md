# Campaigns

> Introduced in PyCRMKit **1.2.0a1**.

Campaigns are CRM-adjacent metadata. PyCRMKit models the business identity and
lifecycle of a Campaign without becoming a marketing-delivery platform.

~~~text
Campaign
├── typed ID
├── stable key
├── name / description
├── lifecycle status
├── optional start/end metadata
├── optional owner
├── revision
└── extensible metadata
~~~

## Quickstart

~~~python
from datetime import UTC, datetime

from pycrmkit import CRM
from pycrmkit.campaigns import CampaignUpdate

crm = CRM.memory()

campaign = crm.campaigns.create(
    key="q4-enterprise",
    name="Q4 Enterprise",
    description="Enterprise outreach metadata",
    starts_at=datetime(2026, 10, 1, tzinfo=UTC),
    ends_at=datetime(2026, 12, 15, tzinfo=UTC),
    metadata={"objective": "pipeline"},
)

campaign = crm.campaigns.update(
    campaign.id,
    CampaignUpdate(name="Q4 Enterprise France"),
    expected_revision=1,
)

campaign = crm.campaigns.activate(
    campaign.id,
    expected_revision=2,
)
~~~

## Lifecycle

~~~text
DRAFT
  ↓ activate
ACTIVE
  ↓ complete
COMPLETED

DRAFT / ACTIVE / COMPLETED
  ↓ archive
ARCHIVED
~~~

Lifecycle mutations are revisioned and can use optimistic preconditions.

## Persistence boundary

1.2.0a1 ships the semantic reference implementation through the Memory adapter.

SQLAlchemy/PostgreSQL and Django Campaign persistence are intentionally
deferred to later 1.2 beta milestones. Unsupported adapters fail closed through
the Campaign capability protocol.

## Explicit boundary

This module does **not** provide:

~~~text
email design
marketing delivery
ad platform management
journey/cadence execution
large-scale campaign orchestration
advanced attribution modelling
~~~

Those concerns remain outside PyCRMKit core.

Campaign membership, Segment targeting, attribution references and
communication linkage are later 1.2 milestones.


## Audience — 1.2.0a2

Campaign audience is intentionally separated into direct membership and Segment
source provenance.

~~~text
Campaign
├── direct members
└── captured Segment sources
        ↓
   final audience
~~~

Direct members are explicit `CampaignMember` records:

~~~python
contact = crm.contacts.create(display_name="Ada")
campaign = crm.campaigns.create(key="launch", name="Launch")

crm.campaigns.add_member(
    campaign.id,
    EntityReference("contact", contact.id),
)
~~~

A Segment source is materialized when attached:

~~~python
segment = crm.segments.create_dynamic(
    key="linkedin",
    name="LinkedIn",
    entity_kind="contact",
    query=Predicate("source", QueryOperator.EQ, "linkedin"),
)

source = crm.campaigns.attach_segment_source(
    campaign.id,
    segment.id,
)
~~~

If the Segment population later changes, the Campaign audience remains
unchanged until:

~~~python
crm.campaigns.refresh_segment_source(
    campaign.id,
    segment.id,
)
~~~

This explicit refresh rule prevents a live Segment edit from silently changing
an already-planned Campaign audience.

Use:

~~~python
crm.campaigns.members(campaign.id)          # direct members only
crm.campaigns.segment_sources(campaign.id)  # source provenance
crm.campaigns.audience(campaign.id)         # de-duplicated final union
crm.campaigns.audience_count(campaign.id)
crm.campaigns.contains(campaign.id, reference)
~~~

The Memory adapter is the semantic reference for these contracts in 1.2.0a2.


## Attribution & communication linkage — 1.2.0a3

Campaign attribution remains reference-oriented rather than analytical.

~~~python
crm.campaigns.add_attribution(
    campaign.id,
    EntityReference("contact", contact.id),
    source="linkedin organic",
    external_ref="utm-2026-q4",
)
~~~

This records provenance only. PyCRMKit does not infer attribution weights,
conversion credit or first/last-touch semantics in this release.

Campaigns may also reference communications that already exist in the CRM:

~~~python
crm.campaigns.link_communication(
    campaign.id,
    communication.id,
    role="follow-up",
)

records = crm.campaigns.communications(campaign.id)
~~~

Communication linkage never sends or queues a message. Delivery remains owned
by the Communication domain and provider adapters.
