"""LOT-32-011: governance preparation cannot silently grant release authority."""

from __future__ import annotations

from pathlib import Path

from pycrmkit import __version__

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_go_no_go_dossier_is_explicitly_pending() -> None:
    dossier = _read("docs/development/1.2.0-stable-lot-32-011-go-no-go.md")
    assert __version__ == "1.2.0"
    assert "Decision now: NO-GO / PENDING MAINTAINER AUTHORIZATION" in dossier
    assert "Decision | **PENDING - NOT APPROVED**" in dossier
    assert "LOT-32-011 is **IN PROGRESS**" in dossier
    assert "LOT-32-012 GitHub publication authorization | **NOT GRANTED**" in dossier
    assert "Separate PyPI publication decision | **NOT AUTHORIZED" in dossier


def test_dossier_requires_exact_sha_review_and_branch_policy() -> None:
    dossier = _read("docs/development/1.2.0-stable-lot-32-011-go-no-go.md")
    for required in (
        "0def9708d3ae139e6cc9b5c5edfec4be61da342e",
        "34/34",
        "105/105",
        "1,248 passed",
        "PostgreSQL 16/17",
        "branch-protection",
        "403",
        "latest PR HEAD",
        "exact `main` SHA",
        "R-09",
        "NOT AUTHORIZED",
    ):
        assert required.casefold() in dossier.casefold(), required
    for issue in range(103, 112):
        assert f"/issues/{issue}" in dossier


def test_runbook_never_confuses_merge_with_publication() -> None:
    runbook = _read("docs/development/1.2.0-stable-lot-32-011-main-merge-runbook.md")
    assert "ONLY AFTER EXPLICIT GO" in runbook
    assert "Do not execute these commands while the decision is pending." in runbook
    assert "exact main SHA" in runbook
    assert "push" in runbook
    assert "do not tag or publish" in runbook
    assert "LOT-32-012" in runbook
    assert "LOT-32-013" in runbook


def test_prepublication_status_and_frozen_rc_evidence() -> None:
    assert "PREPARED / NOT PUBLISHED" in _read("docs/releases/1.2.0.md")
    readme = _read("README.md")
    assert "Release availability:" in readme
    assert "not necessarily published" in readme
    assert "Published stable version: **1.2.0" not in readme
    assert '"target_release": "1.2.0rc1"' in _read(
        "tests/compatibility/public_api_v1_2_campaign_candidate.json"
    )
    workflow = _read(".github/workflows/campaign-stable-go-no-go-preflight.yml")
    assert "pull_request:" in workflow
    assert "release/1.2.0-campaign-metadata-stable" in workflow
    assert "git diff --name-only origin/main...HEAD -- src/pycrmkit/" in workflow
    assert "gh release create" not in workflow
    assert "gh pr merge" not in workflow
    assert "git tag" not in workflow


def test_all_stable_qualification_workflows_run_on_exact_main_push() -> None:
    """A merged main SHA must receive the same dedicated stable gates as the PR."""
    for name in (
        "campaign-stable-compatibility",
        "campaign-stable-cross-adapter-transport",
        "campaign-stable-dataops-qualification",
        "campaign-stable-distribution-qualification",
        "campaign-stable-docs-qualification",
        "campaign-stable-go-no-go-preflight",
        "campaign-stable-persistence-qualification",
        "campaign-stable-reference-host-qualification",
        "campaign-stable-version-promotion",
    ):
        workflow = _read(f".github/workflows/{name}.yml")
        assert "pull_request:" in workflow, name
        assert "push:" in workflow, name
        assert "main]" in workflow, name
        assert "contents: read" in workflow, name
        assert "contents: write" not in workflow, name
