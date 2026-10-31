"""S-T-023..027: development identity must not impersonate frozen v1.2.0."""

from __future__ import annotations

from importlib.metadata import version
from pathlib import Path

from pycrmkit import __version__

ROOT = Path(__file__).resolve().parents[2]

FROZEN_WORKFLOWS = (
    "campaign-stable-compatibility",
    "campaign-stable-cross-adapter-transport",
    "campaign-stable-dataops-qualification",
    "campaign-stable-distribution-qualification",
    "campaign-stable-docs-qualification",
    "campaign-stable-go-no-go-preflight",
    "campaign-stable-persistence-qualification",
    "campaign-stable-reference-host-qualification",
    "campaign-stable-version-promotion",
)


def test_dev_source_has_distinct_pep440_identity() -> None:
    assert __version__ == "1.3.0.dev0"
    assert __version__ != "1.2.0"
    assert version("pycrmkit") == __version__
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = {attr = "pycrmkit.__about__.__version__"}' in project


def test_archived_1_2_promotion_workflows_are_not_dev_pr_gates() -> None:
    for name in FROZEN_WORKFLOWS:
        workflow = (ROOT / ".github/workflows" / f"{name}.yml").read_text(
            encoding="utf-8"
        )
        assert "workflow_dispatch:" in workflow, name
        assert "pull_request:" not in workflow, name
        assert "branches: [main]" not in workflow, name
        assert "contents: write" not in workflow, name


def test_historical_replay_pins_actual_stable_commit_and_tag() -> None:
    workflow = (ROOT / ".github/workflows/historical-v1.2.0-tag-replay.yml").read_text(
        encoding="utf-8"
    )
    assert "ref: v1.2.0" in workflow
    assert "e0ae1c67ccc488918dbef845b799caf7aba3ab70" in workflow
    assert "587d6b806d098b951916b7ad219b08d62ff7ca5c" in workflow
    assert "workflow_dispatch:" in workflow
    assert "gh release create" not in workflow


def test_public_docs_separate_dev_and_published_stable() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    provenance = (
        ROOT / "docs/development/1.3.0/aud-fix-04-release-provenance.md"
    ).read_text(encoding="utf-8")
    for content in (readme, changelog, provenance):
        assert "1.3.0.dev0" in content
        assert "v1.2.0" in content
    assert "PR #115" in provenance and "OPEN" in provenance
    assert "NOT QUALIFIED" in provenance


def test_frozen_release_manifest_contract_remains_named_1_2() -> None:
    inspector = (
        ROOT / "scripts/stable_1_2_distribution_manifest.py"
    ).read_text(encoding="utf-8")
    assert 'assert version == "1.2.0"' in inspector
    assert '"target_stable_version": "1.2.0"' in inspector
