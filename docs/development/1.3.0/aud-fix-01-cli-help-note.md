# AUD-FIX-01 - CLI help regression

This increment corrects the fragile ANSI/Rich formatting assertion in `test_cli_help` while retaining checks for CLI usage, executable name and registered commands.

It is **not** the completion of AUD-FIX-01 or Gate S0. Ruff, mypy, packaging and the entire supported Python test matrix remain separate required checks.

Baseline main SHA: `15140b510506d7822ac38ab36682e1de09ff3b71`.
