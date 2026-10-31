# AUD-FIX-09 - Privacy Governance and Data Processing Boundaries

**Project:** PyCRMKit v1.3.0 - Track S / RC
**Owner:** Host application / deploying data controller; library maintainer owns framework contract documentation
**Status:** IMPLEMENTATION CANDIDATE / NOT A GDPR CERTIFICATION
**Issue:** #126
**Date:** 2026-10-31

## 1. Scope and architectural distinction

PyCRMKit is a headless CRM domain and adapter library, not a controller-facing
host application or automatic privacy-compliance system. Identity, authorization,
retention, legal basis, notices, data subject rights and operational logging
must be configured and verified in each deploying product.

The seven business blueprints under `docs/analysis/` and seven skills under
`.agents/skills/` describe **illustrative** use cases. They do not themselves
establish production functionality or authorize extracting personal information
from Gmail, WhatsApp, social media, forms, payment providers or third-party
groups. This document is engineering guidance, not legal advice.

## 2. Data governance controls (required host obligations)

| Topic | Host decision and implementation evidence |
|---|---|
| Purpose and lawful basis | Inventory each processing purpose and identify and document an appropriate GDPR Art. 6 basis; Art. 9 assessment for special-category data where applicable. Consent is not universal, but must be proven when used or otherwise legally required. |
| Transparency | Provide notices detailing purposes, recipients, rights, controller, retention and contact path before or at collection, as applicable. |
| Minimization | Do not persist full chat transcripts, recordings, passwords, access tokens, CV attachments, payment card details or sensitive raw free text when a reviewed summary, ID and status suffice. |
| Authorization | Enforce tenant and principal boundaries at the host; an `actor_id` from environment/YAML is only a declared audit claim, not authentication. |
| Third parties | Assess contracts, processor/subprocessor obligations, access, transfer mechanisms and APIs before enabling WhatsApp, Microsoft 365, email providers, payment tools or spreadsheet exports. |
| Retention | Define per-purpose periods and disposal triggers at the host; avoid arbitrary global or hard-coded retention promises. Ensure deletion/rectification and backups follow an agreed workflow. |
| Data rights | Provide a documented workflow for access, correction, objection, withdrawal where consent applies, and deletion or restriction subject to lawful exceptions. Audit trails need purpose-limited, access-controlled and appropriately redacted retention. |
| Security | Encrypt and restrict sensitive data at rest/in transit where appropriate, apply least privilege, redact logs, avoid secret-in-URL and raw exception disclosure, review import/export CSV formula injection and backup access. |
| AI and agents | Treat extracted summaries as unverified until reviewed; do not allow unsupervised contact, recording, cross-tenant retrieval or external export via Markdown prompts. |

## 3. Business scenario-specific risks and safeguards

| Scenario | Minimum additional policy |
|---|---|
| WhatsApp agency relationships | Separate personal/social discussions from client data. Capture authorized purpose-limited summaries only. Consent and platform/channel policies must be assessed for message exports and outreach. |
| Alumni directory | Explicitly choose visibility and invitations policy, handle tokenized activation securely at the host, avoid unsolicited cohort-wide disclosure or group broadcasts. |
| Association members | Separate membership, volunteering, finance and IT provisioning purposes. Restrict payment evidence and identity records; deprovision exited members promptly. |
| Freelance recruiting | Keep recruiter and candidate notes relevant to legitimate opportunities, support objections and apply proportionate retention after closure. |
| Public procurement | Separate public organization contact records and restricted bid/commercial content, preserve deadline evidence while minimizing unrelated PII. |
| Student career | Protect student/candidate records, avoid bulk external disclosure and require host authorization for mentor/recruiter outreach. |
| Web agency | Segregate prospects, clients and operational support information, especially call notes, project credentials and maintenance secrets. |

## 4. Demo fixture policy

Documentation may include plausible names, phone formats and business scenarios,
but no example should require actual personal information to be executable.
This remediation replaces emails resembling live personal addresses with
reserved `example.org` fixture addresses in seven analysis blueprints and
seven skill `examples.md` files.

No claim is made that all names, references or phone values are fictional.
Before making any example a tested runnable fixture, review it for accidental
identifiers, production URLs and secrets. Keep real customer records out of
public test artifacts and PR comments.

## 5. Technical contracts and outstanding implementation

**Existing boundaries:** S0 secures local CLI state, database fallbacks and
provider error handling. AUD-FIX-07 proposes mock email disclosure and
actor-claim propagation. These do not implement host authentication, tenant
authorization or subject-rights workflows.

**Still to implement outside this docs-focused PR:**
- host-scoped identity and authorization adapters for sensitive APIs;
- data subject rights and retention integrations, including backup policy;
- testable privacy configurations in host examples and deployment guides;
- review of every public CLI/API/skills example, including `workflow.md`,
  in conjunction with AUD-FIX-05 and the proposed ADR-DX-001;
- tests and threat review for data export, bulk mail and agent tool calling.

## 6. Release and acceptance rules

The release ledger `aud-fix-09-release-evidence-ledger.md` records exact
GitHub SHAs, workflow and check evidence, limitations and gate ownership.
Never backfill or rewrite immutable v1.2.0 historical evidence to make a
v1.3 development build pass. A green CI gate is necessary but does not
replace maintainer authorization, privacy review, post-merge qualification
or a final release-candidate verification.

**RC Gate: NO-GO until privacy, audit evidence, review and release criteria
are explicitly accepted. No new PyPI version, release tag or GitHub Release
is authorized by this document.**
