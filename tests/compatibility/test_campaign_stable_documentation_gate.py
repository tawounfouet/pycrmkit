"""LOT-32-008: release documentation must not pretend that stable is published."""

from __future__ import annotations

from pathlib import Path

from pycrmkit import __version__

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_candidate_package_and_release_docs_remain_prepared() -> None:
    assert __version__ == "1.2.0", "source promoted in LOT-32-009; not published"
    note = _read("docs/releases/1.2.0.md")
    assert "PREPARED / NOT PUBLISHED" in note
    assert "PENDING" in note
    assert "1.2.0rc1" in note
    assert "1.1.0" in note
    assert "PyPI" in note
    assert "0006_campaign_persistence" in note
    assert "0005_communication_record_store" in note

    # The public README is also the PyPI long description: keep it evergreen,
    # with registry links rather than an already-stale prepublication banner.
    readme = _read("README.md")
    assert "## Installation" in readme
    assert "## Quickstart" in readme
    assert "[PyPI](https://pypi.org/project/pycrmkit/)" in readme
    assert "Release availability:" in readme
    assert "not necessarily published" in readme
    assert "Published stable version: **1.2.0" not in readme

    changelog = _read("CHANGELOG.md")
    pre_rc = changelog[: changelog.index("## [1.2.0rc1]")]
    assert "## [Unreleased]" in pre_rc
    assert "## [1.2.0] - PREPARED / NOT PUBLISHED" in pre_rc
    assert "LOT-32-012" in pre_rc
    assert "PyPI" in pre_rc


def test_freeze_provenance_and_navigation() -> None:
    rc = _read("docs/releases/1.2.0rc1.md")
    assert "**PUBLISHED — GITHUB PRERELEASE**" in rc
    assert "5113cedb50750185e457505dfcca5519ce3a62bd" in rc
    assert "a12cc02f854873d7d7f4f095d3eda210e6d2d35bd86cc4477deb3fef2391b59f" in rc
    frozen = _read("tests/compatibility/public_api_v1_2_campaign_candidate.json")
    assert '"target_release": "1.2.0rc1"' in frozen
    assert '"promoted_release": "1.2.0"' in frozen

    nav = _read("mkdocs.yml")
    for path in (
        "releases/1.2.0rc1.md",
        "releases/1.2.0.md",
        "development/1.2.0-stable-release-gate.md",
        "reference/1.2.0-support-and-compatibility.md",
        "getting-started/1.2.0-upgrade.md",
        "data_operations/campaign-recovery.md",
    ):
        assert path in nav


def test_support_contract_is_bounded_not_invented() -> None:
    matrix = _read("docs/reference/1.2.0-support-and-compatibility.md")
    for value in (
        "3.11",
        "3.12",
        "3.13",
        "16 and 17",
        "2.0.x and 2.1.x",
        "0.141",
        "5.2",
        "3.18",
        "No promised support duration",
        "not an atomic bulk import",
        "not snapshot consistent",
    ):
        assert value.lower() in matrix.lower(), value
    runbook = _read("docs/development/1.2.0-stable-release-gate.md")
    for section in (
        "Partial publication recovery",
        "NO-GO",
        "LOT-32-009",
        "LOT-32-010",
        "LOT-32-011",
        "LOT-32-012",
        "LOT-32-013",
        "PyPI",
        "annotated",
    ):
        assert section in runbook
    guide = _read("docs/getting-started/1.2.0-upgrade.md")
    assert "PREPARED / NOT PUBLISHED" in guide
    assert "Do **not** combine" in guide
    assert "Rollback" in guide
