"""LOT-32-001: regression guards for the immutable RC-to-stable baseline.

These tests deliberately avoid network/API calls. GitHub tag, SHA, asset and
main-workflow provenance are verified separately and recorded in the frozen
baseline document. They do not claim that stable v1.2.0 is published.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs/development/1.2.0-stable-baseline-and-scope-freeze.md"
INVENTORY = ROOT / "docs/development/1.2.0-stable-version-reference-inventory.md"
RC_RELEASE = ROOT / "docs/releases/1.2.0rc1.md"
CANDIDATE = ROOT / "tests/compatibility/public_api_v1_2_campaign_candidate.json"

RC_SOURCE = "5113cedb50750185e457505dfcca5519ce3a62bd"
MAIN_OPENING = "2fbfd90a5a25cadb34f0d1e33e207c0f5a4b8ec9"
RC_TAG_OBJECT = "5ae9dec18c41eb456e69ae5e525694fa2129296a"
B3_SOURCE = "76aff8231ee4fe824088951af2e9ce20a0c54f68"


def test_baseline_names_exact_immutable_rc_and_main_commits() -> None:
    evidence = BASELINE.read_text(encoding="utf-8")
    for value in (
        RC_SOURCE,
        MAIN_OPENING,
        RC_TAG_OBJECT,
        B3_SOURCE,
        "v1.2.0rc1",
        "v1.2.0b3",
        "release/1.2.0-campaign-metadata-stable",
        "NOT PUBLISHED",
    ):
        assert value in evidence, value


def test_scope_freeze_explicitly_preserves_domain_and_release_boundaries() -> None:
    evidence = BASELINE.read_text(encoding="utf-8")
    for required in (
        "0 new features",
        "Host",
        "DataOps",
        "SQLAlchemy",
        "Django",
        "1.2.0rc2",
        "LOT-32-002",
        "LOT-32-011",
        "LOT-32-012",
    ):
        assert required.casefold() in evidence.casefold(), required


def test_historical_campaign_manifest_keeps_all_three_version_roles() -> None:
    data = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert data["baseline_release"] == "1.2.0b3"
    assert data["target_release"] == "1.2.0rc1"
    assert data["promoted_release"] == "1.2.0"


def test_inventory_identifies_current_history_mixed_and_rc_workflows() -> None:
    inventory = INVENTORY.read_text(encoding="utf-8")
    for required in (
        "CURRENT=14",
        "MIXED=5",
        "RC-WORKFLOW=3",
        "HISTORICAL=33",
        "src/pycrmkit/__about__.py",
        "tests/compatibility/test_rc1_version_alignment.py",
        ".github/workflows/publish-v1.2.0rc1.yml",
        "tests/contracts/campaign_http/openapi_golden_v1_2.json",
    ):
        assert required in inventory, required


def test_rc_publication_evidence_remains_historical_not_stable_claim() -> None:
    rc_evidence = RC_RELEASE.read_text(encoding="utf-8")
    freeze = BASELINE.read_text(encoding="utf-8")
    assert "PUBLISHED — GITHUB PRERELEASE" in rc_evidence
    assert RC_SOURCE in rc_evidence
    assert "27/27" in rc_evidence
    assert "1.1.0" in freeze
    assert "Stable tag / GitHub release" in freeze
    assert "PyPI" in freeze or "PyPI" in rc_evidence


def test_version_source_is_dynamic_and_not_prematurely_promoted() -> None:
    package_source = (ROOT / "src/pycrmkit/__about__.py").read_text(
        encoding="utf-8"
    )
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = {attr = "pycrmkit.__about__.__version__"}' in project
    # This guard stays valid at the later, separately qualified version flip.
    assert (
        '__version__ = "1.2.0rc1"' in package_source
        or '__version__ = "1.2.0"' in package_source
    )
