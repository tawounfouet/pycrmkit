# AUD-FIX-05 - CLI, README and skill contract inventory

**Date:** 2026-10-31  
**Baseline:** S0 PR #129, `600fddbc29eb2fc0a1ab290e2ea0c03a01791868`  
**Status:** PARTIAL REMEDIATION / NOT QUALIFIED  
**Issue:** #122, Gate S1

## Verified CLI command registration

The authoritative command table is in `.agents/AGENTS.md`, based on
`src/pycrmkit/cli/app.py` and `src/pycrmkit/cli/commands/*.py`.
The README is corrected to stop advertising `pck config show`,
to select explicit local seeding via `pck seed --local`,
and to explain that `pck dashboard --demo` is in-memory.
No new CLI feature is introduced to satisfy documentation.

## Known gaps (deferred)

| Advertised example | Implemented snapshot | Resolution |
|---|---|---|
| `pck config show` | No config group | Removed from runnable README, use `pck --help` |
| `pck leads create` | No leads group | Mark skill illustrative; do not add commands without specification |
| `pck contacts update` / `pck orgs update` | No update command | Mark illustrative; separate feature scope |
| `pck orgs tag` | No orgs tag command | Mark illustrative |
| `pck sales move <id> <stage> --pipeline` | `move` accepts two positional args | Mark illustrative or remove invalid option in future executable example |
| `pck tasks create --title` | `title` positional | Mark illustrative |
| `--due` with hours | Requires `YYYY-MM-DD` | Mark illustrative; no silent timezone truncation |
| `pycrmkit.facade.crm` | Module absent | Use public `from pycrmkit import CRM` |
| `CRM()` with no dependencies | Not supported | Use `CRM.memory()` for demo |
| `crm.timeline.record_note` | Not implemented | Treat as proposed API, not working command |
| `pck tours` from wheel | Source-path dependency at S0 | Addressed separately by AUD-FIX-06 PR #131 |

## Documentation classification

The seven `SKILL.md` entrypoints explicitly classify their recipes as
ILLUSTRATIVE / NOT EXECUTABLE, including the linked workflow and examples.
The `.agents/AGENTS.md` manifest now states the architecture and policy:
the skill files do not create an autonomous execution runtime, scoped
principal, sandbox or actual provider delivery capability.

## Required follow-up before closing AUD-FIX-05

1. Review all 21 skill files, classify each command and Python code sample
   independently as executable, illustrative or deferred.
2. For examples that must become executable, rewrite against real Typer
   signatures and public CRM service contracts; add actual CLI + Python tests.
3. Check privacy and user authorization for communication and exports.
4. Verify wheel/sdist-installed CLI paths and docs on the final SHA.
5. Obtain the maintainer and security reviewer GO; merge only after S0.

This PR fixes misleading claims but does not yet prove full skill
executability or satisfy the whole AUD-FIX-05 Definition of Done.
