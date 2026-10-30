"""LOT-32-009: source promotion is separate from publication and frozen RC evidence."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
STABLE_VERSION = "1.2.0"
RC_VERSION = "1.2.0rc1"

CURRENT = (
    "src/pycrmkit/__about__.py",
    "tests/test_version.py",
    "tests/smoke/test_import.py",
    "tests/smoke/test_public_api.py",
    "tests/e2e/test_data_operations_rc.py",
    "tests/e2e/test_v1_production_qualification.py",
    "scripts/smoke_test.py",
    "examples/django/smoke.py",
    ".github/workflows/compatibility-matrix.yml",
    ".github/workflows/django-e2e.yml",
    ".github/workflows/django.yml",
    ".github/workflows/drf.yml",
    ".github/workflows/production-installed-artifact.yml",
    ".github/workflows/production-qualification.yml",
)


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_source_installed_metadata_and_current_controls_are_stable() -> None:
    assert pycrmkit.__version__ == STABLE_VERSION
    assert importlib.metadata.version("pycrmkit") == STABLE_VERSION
    for path in CURRENT:
        content = _read(path)
        assert RC_VERSION not in content, path
        assert "1.2.0b3" not in content, path
        assert STABLE_VERSION in content, path


def test_rc_only_workflows_remain_archival_and_do_not_run_on_stable_pr() -> None:
    for path in (
        ".github/workflows/campaign-rc1-distribution-qualification.yml",
        ".github/workflows/campaign-rc1-production-host.yml",
    ):
        workflow = _read(path)
        assert "workflow_dispatch:" in workflow, path
        assert "branches: [main]" not in workflow, path
        assert "pull_request:" not in workflow, path
        assert RC_VERSION in workflow, path
    assert "workflow_dispatch:" in _read(".github/workflows/campaign-rc1-exact-main-evidence.yml")


def test_frozen_candidate_and_publisher_keep_original_rc_identity() -> None:
    frozen = _read("tests/compatibility/public_api_v1_2_campaign_candidate.json")
    assert '"target_release": "1.2.0rc1"' in frozen
    assert '"promoted_release": "1.2.0"' in frozen
    assert 'VERSION = "1.2.0rc1"' in _read("scripts/rc1_release_bundle.py")
    assert '"1.2.0rc1"' in _read(".github/workflows/campaign-rc1-distribution-qualification.yml")
    assert "1.2.0rc1" in _read(".github/workflows/publish-v1.2.0rc1.yml")


def test_promotion_never_claims_stable_publication() -> None:
    assert "PREPARED / NOT PUBLISHED" in _read("docs/releases/1.2.0.md")
    assert "Current stable version: **1.1.0" in _read("README.md")
    assert "## [1.2.0] - PREPARED / NOT PUBLISHED" in _read("CHANGELOG.md")
    assert "PENDING LOT-32-011/012" in _read("docs/releases/1.2.0.md")
