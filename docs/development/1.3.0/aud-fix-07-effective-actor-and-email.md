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

## Still required for AC-S1-07 and full AUD-FIX-07

Dashboard currency grouping, >100 opportunity and >50 campaign/task cases,
stage provenance and incomplete-data indications. Then review exact-SHA CI,
security/quality tests and a separate maintainer S1 decision.

Do not merge or publish on the strength of this partial remediation.
