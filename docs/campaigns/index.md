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

Memory remains the semantic reference implementation for Campaign behavior.

From **1.2.0b1**, the complete Campaign contract is also available through the
SQLAlchemy/PostgreSQL adapter:

~~~text
Campaign
├── metadata + lifecycle + revision
├── direct members
├── Segment source provenance
├── captured Segment members
├── attribution references
└── communication links
~~~

All Campaign SQLAlchemy repositories participate in the existing
`SQLAlchemyUnitOfWork`; repository methods do not commit independently.

Django Campaign persistence remains deferred to `1.2.0b2`.

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



## SQLAlchemy/PostgreSQL persistence — 1.2.0b1

The public facade does not change when switching from Memory to SQLAlchemy.

~~~text
crm.campaigns
      ↓
Campaign services
      ↓
Campaign repository contracts
      ↓
SQLAlchemy Campaign adapters
      ↓
PostgreSQL
~~~

Persistence uses six Campaign-owned tables:

~~~text
pycrmkit_campaigns
pycrmkit_campaign_members
pycrmkit_campaign_segment_sources
pycrmkit_campaign_segment_members
pycrmkit_campaign_attributions
pycrmkit_campaign_communication_links
~~~

Campaign updates use revision compare-and-swap so concurrent stale writers
cannot silently overwrite a committed revision.

Final audience queries are computed from a SQL `UNION` of direct members and
captured Segment members. The adapter does not persist a denormalized
"final audience" table.

Alembic head for the SQLAlchemy adapter is now:

~~~text
0005_segmentation_persistence
          ↓
0006_campaign_persistence
~~~

Revision `0006` is additive and preserves existing 1.1 data. Cross-aggregate
references to Segment, CommunicationRecord, Contact, Organization, Lead and
Opportunity remain reference-only rather than database foreign keys.


## Django ORM Campaign persistence — 1.2.0b2

The existing headless `crm.campaigns` facade runs with
`DjangoTransactionBridge`, backed by typed codecs and native Campaign
repositories for definitions, audiences, and attribution/communication linkage.

Django migration `0004_campaign_persistence` introduces six Campaign tables;
`0005_communication_record_store` provides transactional native
`CommunicationRecord` lookup/save and record-existence validation for links.
This **does not** implement the full Communication repository, outbound email
sending or delivery events. No Campaign HTTP endpoint is introduced by b2.

Django uses an internal `BigAutoField` for Segment source rows and a real
`source_id` FK for captured members, whereas SQLAlchemy uses a composite
source identity. **Do not manage the same physical tables with both Alembic
and Django migrations.** Django ORM `models.CASCADE` is not a promise of
PostgreSQL-native `ON DELETE CASCADE`.

See [Django Integration](../integrations/django.md) and
[1.2.0b2 release notes](../releases/1.2.0b2.md).
