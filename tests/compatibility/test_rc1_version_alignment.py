"""LOT-31-015: current-version alignment without rewriting release history.

Only current-version assertions and new candidate packaging are promoted.
Frozen historical manifests retain their b3 baseline on purpose.
"""

from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
RC_VERSION = "1.2.0rc1"  # archived provenance, not current package version
STABLE_VERSION = "1.2.0"
# These files contain *live* installed/source-version assertions or distribution
# filenames. They may never silently refer to the old beta when preparing RC1.
CURRENT_CONTROLS = (
    "src/pycrmkit/__about__.py",
    "tests/test_version.py",
    "tests/smoke/test_import.py",
    "tests/smoke/test_public_api.py",
    "tests/e2e/test_data_operations_rc.py",
    "tests/e2e/test_v1_production_qualification.py",
    "scripts/smoke_test.py",
    "examples/django/smoke.py",
    ".github/workflows/compatibility-matrix.yml",
    ".github/workflows/production-installed-artifact.yml",
    ".github/workflows/production-qualification.yml",
    ".github/workflows/django-e2e.yml",
    ".github/workflows/django.yml",
    ".github/workflows/drf.yml",
)


def test_current_stable_version_is_single_source_of_truth() -> None:
    assert pycrmkit.__version__ == STABLE_VERSION
    assert importlib.metadata.version("pycrmkit") == STABLE_VERSION
    assert f'__version__ = "{STABLE_VERSION}"' in (ROOT / "src/pycrmkit/__about__.py").read_text(
        encoding="utf-8"
    )
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = {attr = "pycrmkit.__about__.__version__"}' in project


def test_current_version_controls_are_stable_not_prerelease() -> None:
    for relative in CURRENT_CONTROLS:
        content = (ROOT / relative).read_text(encoding="utf-8")
        assert "1.2.0b3" not in content, relative
        assert RC_VERSION not in content, relative
        assert STABLE_VERSION in content, relative


def test_frozen_campaign_manifest_preserves_beta_baseline_and_rc_target() -> None:
    path = ROOT / "tests/compatibility/public_api_v1_2_campaign_candidate.json"
    candidate = json.loads(path.read_text(encoding="utf-8"))
    assert candidate["baseline_release"] == "1.2.0b3"
    assert candidate["target_release"] == RC_VERSION
    assert candidate["promoted_release"] == "1.2.0"


def test_release_documentation_records_qualified_github_publication() -> None:
    note = (ROOT / "docs/releases/1.2.0rc1.md").read_text(encoding="utf-8")
    assert "PUBLISHED - GITHUB PRERELEASE" in note
    assert "https://github.com/tawounfouet/pycrmkit/releases/tag/v1.2.0rc1" in note
    assert "5113cedb50750185e457505dfcca5519ce3a62bd" in note
    assert "27/27" in note
    assert "not published by this workflow" in note
    assert "LOT-31-016" in note
    assert (ROOT / "docs/development/1.2.0rc1-qualification-matrix.md").is_file()
    template = (ROOT / "docs/development/1.2.0rc1-go-no-go-template.md").read_text(encoding="utf-8")
    # Keep the pre-publication template as an immutable audit example; the
    # actual final decision and asset fingerprints live in the release notes.
    assert "Historical pre-publication TEMPLATE" in template
    assert "**Outcome:** `UNDECIDED`" in template
    # Historical publish workflows are not edited to point to rc1.
    for name in ("b2", "b3"):
        workflow = ROOT / f".github/workflows/publish-v1.2.0{name}.yml"
        assert workflow.is_file()
        assert "1.2.0rc1" not in workflow.read_text(encoding="utf-8")
