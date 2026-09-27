"""Executable contract for V1 full-production qualification scenarios."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(
    (Path(__file__).with_name("production_scenarios_v1.json")).read_text(
        encoding="utf-8"
    )
)

REQUIRED_LAYERS = {
    "unit",
    "contract",
    "adapter",
    "integration",
    "e2e",
    "smoke",
    "migration",
    "security",
    "performance",
    "compatibility",
}

REQUIRED_CAPABILITIES = {
    "contacts",
    "organizations",
    "relationships",
    "activities",
    "timeline",
    "tasks",
    "leads",
    "opportunities",
    "pipelines",
    "email",
    "webhooks",
    "external_identities",
    "import",
    "dedup",
    "merge",
    "export",
    "postgresql",
    "fastapi",
    "django",
    "drf",
}

REQUIRED_SCENARIOS = {
    "core-relationship-lifecycle",
    "activity-timeline-followup",
    "sales-lifecycle",
    "communication-email-history",
    "event-webhook-delivery",
    "data-operations-roundtrip",
    "fastapi-postgresql-application",
    "django-drf-postgresql-application",
}


def test_target_and_baseline_are_frozen_for_rc_contract() -> None:
    assert MANIFEST["target_release"] == "1.0.0rc1"
    assert MANIFEST["baseline_release"] == "1.0.0b3"
    assert MANIFEST["status"] == "qualification-contract"
    assert MANIFEST["qualification_mode"] == "full-system-no-new-capability"


def test_rc_policy_forbids_feature_scope_and_premature_version_bump() -> None:
    policy = MANIFEST["policy"]

    assert policy["new_features_allowed"] is False
    assert policy["architectural_redesign_allowed"] is False
    assert policy["candidate_version_bump_requires_all_gates"] is True
    assert policy["blocking_failure_requires_new_candidate"] is True


def test_required_qualification_layers_are_complete() -> None:
    assert set(MANIFEST["required_layers"]) == REQUIRED_LAYERS


def test_reference_scenarios_are_unique_and_fully_specified() -> None:
    scenarios = MANIFEST["scenarios"]
    ids = [scenario["id"] for scenario in scenarios]

    assert len(ids) == len(set(ids))
    assert set(ids) == REQUIRED_SCENARIOS
    assert all(scenario["status"] == "specified" for scenario in scenarios)
    assert all(scenario["baseline_evidence"] for scenario in scenarios)
    assert all(scenario["rc_execution_targets"] for scenario in scenarios)


def test_reference_scenarios_cover_all_required_capabilities() -> None:
    covered = {
        capability
        for scenario in MANIFEST["scenarios"]
        for capability in scenario["capabilities"]
    }

    assert covered == REQUIRED_CAPABILITIES


def test_all_baseline_evidence_paths_exist() -> None:
    evidence = {
        path
        for scenario in MANIFEST["scenarios"]
        for path in scenario["baseline_evidence"]
    }

    missing = sorted(path for path in evidence if not (ROOT / path).is_file())
    assert missing == []


def test_rc02_cross_layer_e2e_is_executable_from_source_and_wheel() -> None:
    rc02 = MANIFEST["rc02_cross_layer_e2e"]

    assert rc02["status"] == "implemented"
    assert rc02["scope"] == "framework-agnostic-headless-system"
    assert set(rc02["execution_targets"]) == {"source", "installed-wheel"}
    assert set(rc02["covered_scenarios"]) == {
        "core-relationship-lifecycle",
        "activity-timeline-followup",
        "sales-lifecycle",
        "communication-email-history",
        "event-webhook-delivery",
        "data-operations-roundtrip",
    }
    assert set(rc02["deferred_to_later_rc_gates"]) == {
        "sqlalchemy-postgresql",
        "fastapi-postgresql",
        "django-drf-postgresql",
    }

    missing = sorted(
        path for path in rc02["evidence"] if not (ROOT / path).is_file()
    )
    assert missing == []
