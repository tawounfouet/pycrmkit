#!/usr/bin/env bash
# S0 local qualification fallback; never tag, publish or touch production.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
head="$(git rev-parse HEAD)"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: clean checkout required for exact SHA qualification" >&2
  exit 2
fi
for py in python3.11 python3.12 python3.13; do
  command -v "$py" >/dev/null || { echo "Missing $py" >&2; exit 2; }
done
work="$(mktemp -d /tmp/pycrmkit-s0.XXXXXXXX)"
trap 'rm -rf "$work"' EXIT
first=""
for command in python3.11 python3.12 python3.13; do
  venv="$work/test-$command"
  "$command" -m venv "$venv"
  "$venv/bin/python" -m pip install --upgrade pip
  "$venv/bin/python" -m pip install -e ".[dev]"
  "$venv/bin/python" -m pytest -q -m "not postgresql"
  "$venv/bin/python" -m ruff check .
  "$venv/bin/python" -m mypy src/pycrmkit
  if [[ -z "$first" ]]; then first="$venv/bin/python"; fi
done
"$first" -m build --outdir "$work/dist"
"$first" -m twine check "$work"/dist/*
wheel="$work/dist/pycrmkit-1.3.0.dev0-py3-none-any.whl"
test -s "$wheel"
test -s "$work/dist/pycrmkit-1.3.0.dev0.tar.gz"
for command in python3.11 python3.12 python3.13; do
  venv="$work/installed-$command"
  "$command" -m venv "$venv"
  "$venv/bin/python" -m pip install --upgrade pip
  "$venv/bin/python" -m pip install "$wheel[cli]"
  (
    cd "$work"
    PYTHONPATH="" "$venv/bin/python" -c '
import importlib.metadata as m
import pycrmkit
assert pycrmkit.__version__ == "1.3.0.dev0"
assert m.version("pycrmkit") == pycrmkit.__version__
assert "cli" in m.distribution("pycrmkit").metadata.get_all("Provides-Extra", [])
'
    for cli in pck pycrm pycrmkit; do
      PYTHONPATH="" "$venv/bin/$cli" version --json > "$work/version.json"
      "$venv/bin/python" -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as stream:
    obj = json.load(stream)
assert obj["pycrmkit"]["version"] == "1.3.0.dev0"
' "$work/version.json"
    done
    "$venv/bin/python" -m pip check
  )
done
if ! printenv PYCRMKIT_TEST_POSTGRES_URL >/dev/null; then
  echo "INCOMPLETE: dedicated localhost PostgreSQL pycrmkit_s0_guard required."
  echo "Set PYCRMKIT_TEST_POSTGRES_URL and rerun. No S0 GO established."
  exit 3
fi
"$first" -m pytest -q tests/integrations/test_cli_postgresql_no_mutation.py -m postgresql
echo "Local tests passed for $head. GitHub Actions and provenance remain required."
