"""Qualification contract for the V1 stable promotion."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.v1_stable_release_gate import assert_stable_release_gate

ROOT = Path(__file__).resolve().parents[2]
GATE = json.loads(
    (ROOT / "tests/qualification/stable_release_gate_v1.json").read_text(
        encoding="utf-8"
    )
)


def test_stable_gate_promotes_only_the_qualified_rc() -> None:
    result = assert_stable_release_gate()

    assert result["source_candidate"] == "1.0.0rc1"
    assert result["target_release"] == "1.0.0"
    assert str(result["package_version"]).startswith("1.")
    assert result["functional_delta"] == "none"
    assert result["blocking_failures_allowed"] == 0
    assert result["migration_head"] == "0003"
    assert result["candidate_qualified"] is True
    assert GATE["status"] == "qualified"
    assert GATE["promotion_ready"] is True


def test_stable_policy_forbids_functional_delta() -> None:
    policy = GATE["policy"]

    assert policy["new_features_allowed"] is False
    assert policy["new_public_api_allowed"] is False
    assert policy["persistence_schema_change_allowed"] is False
    assert policy["migration_change_allowed"] is False
    assert policy["stable_artifacts_must_be_reproducible"] is True
