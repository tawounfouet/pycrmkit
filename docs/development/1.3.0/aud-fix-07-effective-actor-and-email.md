# AUD-FIX-07 - Effective CLI actor identity and email provider

**Track:** S1
**Issue:** #124
**Status:** IMPLEMENTATION CANDIDATE / NO-GO
**Baseline:** unmerged S0 candidate 600fddbc29eb2fc0a1ab290e2ea0c03a01791868

## Decision and implementation

`get_crm_context()` and `build_crm_from_store()` now resolve the default
actor through `resolve_actor_id()`, respecting environment or YAML settings.
An explicit actor argument overrides that claim, and the CRM facade passes it
into audit/event context.

An actor configured by environment or YAML is a **declared identifier**, not
a verified human or machine principal. It grants no authorization. The
host application owns authentication, permissions, tenant checks and consent.

`pck doctor --json` includes a safe actor-source diagnostic without exposing
the configured actor string. It also identifies the **effective** email
transport as `mock-cli-mailer`. That transport simulates email acceptance
without sending email. A YAML email provider setting does not imply that
the CLI itself uses a real external provider.

S0 already corrected doctor handling of unreachable explicitly requested
databases and the supported Python range. Those protections remain in force.

## Contract tests

- Configured actor survives into the audit record of a created contact.
- Explicit actor argument takes precedence.
- Doctor reports the effective mock transport with a no-delivery warning.

## Dashboard visibility and currency integrity

The executive dashboard now groups monetary values by currency rather
than pretending that EUR and USD can be added. It derives visible stages
from the observed `pipeline_id` / `stage_id` pairs instead of four
hard-coded demo stages. Weighted amounts use each opportunity's actual
probability, and the distribution bars represent the percentage of
sampled deals by stage, not a fictitious cross-currency monetary ratio.

When the first 100 opportunities, 50 campaigns or 50 tasks omit records,
the CLI explicitly shows `PARTIAL RESULTS`, visible counts and totals.
In all cases the header calls these observed read-only metrics, not a
complete or real-time Customer 360 view. Campaign reach counts
memberships (which can repeat across campaigns), not unique people.
Unknown campaign budget currencies are not labelled EUR.

Persistent database connection strings are no longer printed in the
dashboard header.

## Additional tests and remaining qualification

- Verify mixed EUR/USD arithmetic and weighted totals.
- Verify explicit partial warning with a mocked page total above 100.
- Verify normal seed/demo does not falsely claim complete Customer 360.
- Verify the exact final SHA on all CI workflows and installed distributions.

**Still required:** broader >100 opportunity and >50 campaign/task integration
qualification across Memory, SQLAlchemy and Django, and review of whether
dedicated read aggregation ports should replace current bounded
client-side scans. No change here grants an authenticated principal.

**Gate S1: NO-GO** until maintainer and security review. No release or merge.
