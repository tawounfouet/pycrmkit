# ADR-DX-001 - CLI, Customer 360 and agent playbook boundaries

**Project:** PyCRMKit 1.3.0  
**Track:** S1 - Developer Experience & Agent Playbooks  
**Audit remediation:** AUD-FIX-08 (AUD-012 / AUD-013)  
**Related:** LOT-33-002, C0, GATE-S1, issue #125  
**Date:** 2026-10-31  
**Status:** PROPOSED - pending maintainer, domain/API and security review  
**Base reviewed:** S0 candidate `600fddbc29eb2fc0a1ab290e2ea0c03a01791868`  
**Implementation status:** Decision proposal only; no runtime or public Customer 360 API is implemented by this ADR.

## 1. Context and problem

PyCRMKit is a headless, framework-agnostic CRM domain library. Its existing
facade, domain services, repository protocols and Memory / SQLAlchemy / Django
adapters predate the new CLI and agent guides.

The 2026-10-31 audit identified two boundary failures:

- `src/pycrmkit/cli/state.py` accesses `crm._runtime.uow_factory()` for some
  query paths. This is private coupling, not a stable public read contract.
- The CLI currently implements bounded client-side scans for some CRM views;
  these cannot be represented as a complete, authorized Customer 360 query.
- The repository contains `.agents/` role prompts and skills, but no
  qualified autonomous execution runtime, tool sandbox or permission engine.
- Some README and skill examples advertise commands or capabilities not
  registered by the CLI. `pck config show`, for instance, is shown in the
  README, but no `config` sub-application is registered in
  `src/pycrmkit/cli/app.py` at the reviewed SHA.
- The CLI uses `MockCliEmailProvider` for demonstration. A successful mock
  response must not be described as verified provider delivery.

The Track S S0 branch addresses the security of CLI local state and
configuration. S0 qualification does not establish the interfaces and trust
boundaries required by S1 or Customer 360.

## 2. Decision (proposed)

### 2.1 Four separate layers

1. **CRM core and domain:** own business invariants, entities, mutation
   services, domain events and typed public contracts. No Typer, Rich, HTTP
   framework, agent runtime or database-specific dependency is mandatory.
2. **Customer 360 read application service:** a read-only composition layer,
   subject to C0 and its separate ADRs. It depends on small, typed read ports
   and returns DTOs. It never creates or modifies CRM domain records.
3. **CLI / HTTP presentation adapters:** optional clients of public CRM
   application services. They parse input, display output and map errors and
   exit codes. They do not reach into `crm._runtime` or ORM sessions to
   implement application behavior.
4. **Agent playbooks:** `.agents/` contains documentation and operational
   recipes for externally operated assistants. It is not executable,
   authenticated or sandboxed agent infrastructure delivered by PyCRMKit.

```text
Host application (principal, tenant, policy, consent)
                   |
       verified application context
                   |
        +----------+-----------+
        |                      |
    CLI adapter           HTTP adapter
    (optional)            (optional)
        |                      |
        +----------+-----------+
                   |
         Public CRM facade / services
                   |
       +-----------+-----------+
       |                       |
  Domain commands      Customer 360 reads
                       (proposed; C0 gate)
       |                       |
       +-----------+-----------+
                   |
        Typed repository / query ports
                   |
           Memory | SQLAlchemy | Django

.agents/ -> human or external-agent instructions -> approved public tools
          (never a direct privileged shortcut to private runtime)
```

### 2.2 Customer 360 ownership and scope

Customer 360 is a Contact-oriented CQRS **read model**, not a new aggregate
root, separate source of truth or generic CRM data warehouse. It composes
existing Contact, Organization, Relationship, Activity, Task, Timeline,
Opportunity, Segment and Campaign records only through supported query
contracts. The exact namespace, immutable DTO types, partial-result semantics,
authorization model and pagination are **not** frozen here and require
ADR-C360-001..004 and an approved C0 gate.

Until C0, documentation and examples must label any
`crm.customer360.execute(...)` signature as **candidate pseudocode**.
No Customer 360 functionality may be claimed based only on today's
`pck contacts show` or `pck orgs show` output.

### 2.3 Public query-port rule

The CLI must consume documented public facade/query services. If a required
read or aggregation operation is absent, either:

- introduce a minimal typed port under a separately reviewed API change,
  with Memory, SQLAlchemy and Django conformance tests; or
- keep the feature explicitly partial/deferred, without a false completeness
  claim.

Do not re-export `crm._runtime`, leak a SQLAlchemy session or scan a fixed
prefix of rows to imitate a complete reverse query. Queries require stable
ordering, bounded pages, truthful totals, tenant/actor scoping and explicit
errors for unsupported/failed reads. Count semantics must be documented.

### 2.4 Identity and authorization

The **host** owns authentication, tenant identity, authorization and consent.
A CLI string such as `CRM_ACTOR_ID` is a claimed audit actor and is **not**
proof of an authenticated principal. It may be recorded only with accurate
provenance and no false security guarantee.

For any sensitive read or mutation: validate configuration, resolve a trusted
context, authorize before fetching PII, return a non-success result on denial,
redact secrets from outputs and logs, and preserve an auditable record where
the public contract requires one. Unknown backends and authorization
failures must fail closed; a fallback to local/demo storage is not allowed.

### 2.5 Agent tool policy

- **Read:** agent guidance may call documented public read APIs only within
  host-approved principal/tenant scopes, with PII minimized.
- **Write:** creation, update, outreach, export, deletion and bulk actions
  require explicit host policy and human confirmation where the impact or
  sensitivity warrants it. A markdown prompt cannot grant a permission.
- **External effects:** emails, webhooks and provider calls require a
  configured, qualified adapter. A mock result is not external delivery.
- **Execution:** no arbitrary Python, shell or database tool is shipped as an
  implicitly trusted autonomous capability. Any future runtime, sandbox or
  delegated identity support requires a separate design, threat model and
  release milestone.
- **Disclosure:** examples handling recruiting, WhatsApp, alumni or
  customer records must specify data purpose, access constraints, retention
  and approval boundaries.

### 2.6 Distribution and truth-in-documentation

The core installation remains independent of CLI and agent frameworks. The
`cli` extra and `pck` / `pycrm` entry points must be validated against
the installed wheel/sdist, not only the source checkout. Feature tours are
distributable only when their resource paths work outside the repository;
otherwise they are source-only and visibly labelled as such.

Classify each example as:

- **EXECUTABLE:** supported commands/signatures and passing acceptance tests.
- **ILLUSTRATIVE:** labelled pseudocode, not presented as runnable.
- **DEFERRED:** unsupported capability with a tracked work item.

Avoid marketing language such as "autonomous agent ecosystem" or
"production-grade" for undocumented or unqualified behavior.

## 3. Alternatives considered

| Option | Result | Rationale |
|---|---|---|
| Make CLI the main CRM API | Rejected | Couples the domain library to a presentation tool. |
| Expose `crm._runtime` as public | Rejected | Freezes private plumbing, violates DIP/SoC and leaks persistence concerns. |
| Implement Customer 360 inside CLI | Rejected | Prevents reuse, shared authorization and backend conformance. |
| Treat `.agents/` as a full agent runtime | Rejected for 1.3 | No qualified execution, policy, sandbox or authorization infrastructure. |
| Build specialized read ports behind facade | Preferred | Small interfaces, testable behavior, adapters remain replaceable. |
| Defer unsupported commands and scripts | Preferred when appropriate | Prevents inventing unplanned business features for documentation parity. |

## 4. Consequences and engineering tasks

| Work item | Change to implement | Evidence / contract |
|---|---|---|
| AUD-FIX-05 | Inventory registered CLI commands and all runnable examples; repair or relabel mismatches | AC-S1-01/02, CLI help/exit-code and example tests |
| AUD-FIX-06 | Package tours as resources or explicitly make them source-only | AC-S1-03/04, isolated wheel + sdist tests |
| AUD-FIX-07 | Propagate validated actor provenance; distinguish mock email; truthful doctor and KPIs | AC-S1-05..08, negative and large-dataset tests |
| AUD-FIX-08 | Replace private CLI read paths with public read contracts; retain clear agent boundaries | AC-S1-09/10, facade/adapter contract review |
| LOT-33-002 | Approve Customer 360 API/security/consistency ADRs before any C0 implementation GO | AC-C0-05..07 and C0 sign-off |
| AUD-FIX-09 | Data minimization, purpose/retention guidance and evidence ledger | Privacy review, docs and examples |

None of these rows is automatically complete because this document exists.

## 5. Security and compatibility invariants

- Read-only Customer 360 must emit no command-side domain mutation or email.
- A denied sensitive lookup must not disclose existence, totals or PII.
- `empty` must not mask `unavailable`, `redacted` or technical failure.
- Actor claims may not be confused with host-authenticated identity.
- JSON CLI state and explicit persistent-backend selection remain S0 invariants.
- Public V1 / V1.1 / V1.2 behavior is compatibility-governed.
- No new mandatory dependency, backend-specific type or hidden ORM query leaks
  into the core.
- Claims about agent tools, installed tours and provider calls are backed by
  runnable tests or marked as limitations.

## 6. Proposed acceptance and review checklist

- [ ] Maintainer accepts the four-layer ownership and `.agents/` designation.
- [ ] Domain/API reviewer confirms public facade boundary and C0 ADR dependencies.
- [ ] Security reviewer approves principal, scope, consent and write-tool policy.
- [ ] CLI inventory / documentation matrix links each command to a real help
      signature or explicitly non-runnable example.
- [ ] Private `crm._runtime` reads are removed or isolated under a scoped,
      tested, reviewed plan; no unsupported public Customer 360 promises.
- [ ] Installed-wheel CLI, docs/skills examples and agent boundaries pass
      their relevant acceptance tests on the exact final candidate SHA.
- [ ] S0 remains qualified after integration, and S1 GO is separately recorded.

## 7. Release and rollout

This ADR is **proposed**, not `ACCEPTED`. It can be reviewed in an isolated
documentation PR stacked on the S0 candidate. Do not merge it into `main`
ahead of an authorized S0 promotion. The final accepted decision becomes a
prerequisite for the C0 API freeze and for S1 acceptance.

No tag, prerelease, stable release or PyPI publication is authorized here.

## 8. References

- `00_PYCRMKIT_PROJECT_VISION_AND_ARCHITECTURE.md`
- `03_PYCRMKIT_TESTING_AND_QUALITY_STRATEGY.md`
- `04_PYCRMKIT_PERSISTENCE_AND_ADAPTER_CONTRACTS.md`
- `07_PYCRMKIT_AUDIT_TECHNIQUE_POST_ANTIGRAVITY_2026-10-31.md`
- `11_PYCRMKIT_V1_3_0_IMPLEMENTATION_PLAN_AND_ACCEPTANCE.md`, section 6
- `docs/development/1.3.0/s0-qualification-progress.md`
- `src/pycrmkit/cli/app.py`, `src/pycrmkit/cli/state.py`
- GitHub PR #129, issue #125
