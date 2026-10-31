# PyCRMKit Agent Playbooks - scope and execution policy

**Status:** DOCUMENTATION ONLY / ILLUSTRATIVE / NOT EXECUTABLE as a complete workflow
**Track:** PyCRMKit 1.3.0, AUD-FIX-05 and AUD-FIX-08
**Scope:** Six role guides and seven skill collections

## What exists

PyCRMKit provides a CRM domain library with a public Python API plus an
optional Typer/Rich CLI. The files in `.agents/agents/` and
`.agents/skills/` describe candidate business workflows for *external*
assistants and human maintainers. They do **not** provide an autonomous
agent runtime, scheduler, sandbox, authenticated principal, tool gateway
or implicit authority to read or mutate personal data.

Some `SKILL.md`, `workflow.md` and `examples.md` snippets describe
**proposed** commands, domain methods or integrations that have **not**
been implemented in the shipped CLI or public facade. Such snippets are
illustrations only and MUST NOT be presented or executed as verified commands.

## Safe execution principles

1. Inspect `pck --help` and each subcommand's `--help` in the installed
   version before assuming a command is available.
2. For Python, use documented public APIs such as
   `from pycrmkit import CRM` and explicit `CRM.memory()`; do not use
   the absent `pycrmkit.facade.crm` module or `CRM()` without the
   required injected dependencies.
3. Where a method or workflow is not implemented, label it *pseudocode*
   and create a separate approved feature request rather than fabricating
   a CLI command.
4. The host application is responsible for authentication, tenant and
   actor authorization, lawful processing and consent.
5. Treat outreach, exports, writes, deletions and sensitive reads as
   privileged operations requiring host authorization and appropriate
   human confirmation. A markdown guide cannot override these controls.
6. Mock email providers and in-memory demo data do not demonstrate external
   delivery or durable production writes.
7. Maintain evidence of installed wheel/sdist, exact SHA, CLI help and
   integration tests before reclassifying an example as executable.

## Concrete CLI inventory at S0 candidate SHA

| Group | Commands registered |
|---|---|
| Top-level | `dashboard`, `seed`, `reset`, `version`, `doctor`, `tours`, `demo` |
| `contacts` | `list`, `create`, `show` |
| `orgs` | `list`, `create`, `show` |
| `sales` | `pipelines`, `opps`, `move`, `create` |
| `tasks` | `list`, `create`, `complete` |
| `campaigns` | `list`, `create`, `activate`, `complete`, `audience` |
| `migrate` | `upgrade`, `downgrade`, `check`, `current` |

Examples **not** supported in this snapshot:
`pck config show`, `pck leads create`, `pck orgs update`,
`pck contacts update`, `pck orgs tag`,
`pck sales move <id> <stage> --pipeline ...`,
`pck tasks create --title ...`, and passing a date-time where
the `--due` option requires `YYYY-MM-DD`.

## Role guide directory

- agency-copilot
- alumni-network-manager
- association-coordinator
- freelance-hunter
- student-career-coach
- tender-bid-manager

## Acceptance and migration

The seven `SKILL.md` entrypoints must warn that their steps are not
executable as written. Associated `workflow.md` and `examples.md`
inherit this disclaimer. Subsequent work must provide tested, corrected
runnable examples with CLI and public API conformance, or keep them
explicitly non-executable. See AUD-FIX-05 (#122), AUD-FIX-08 (#125),
the proposed ADR-DX-001 (#130) and S1 qualification.

**No claim of S1 acceptance or production agent support is made here.**
