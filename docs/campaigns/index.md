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
