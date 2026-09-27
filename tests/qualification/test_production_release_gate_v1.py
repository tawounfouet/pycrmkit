"""Executable contract for the V1 production release gate."""

from __future__ import annotations

import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

GATE = json.loads(
    (HERE / "production_release_gate_v1.json").read_text(encoding="utf-8")
)
SCENARIOS = json.loads(
    (HERE / "production_scenarios_v1.json").read_text(encoding="utf-8")
)

EXPECTED_PREREQUISITES = {
    "1.0.0a1",
    "1.0.0b1",
    "1.0.0b2",
    "1.0.0b3",
}

EXPECTED_RC_GATES = {
    "RC-01",
    "RC-02",
    "RC-03",
    "RC-04",
    "RC-05",
    "RC-06",
    "RC-07",
}

IMPLEMENTED_RC_GATES = {"RC-01", "RC-02", "RC-03", "RC-04", "RC-05"}


def test_gate_and_scenario_contract_target_the_same_candidate() -> None:
    assert GATE["target_release"] == SCENARIOS["target_release"] == "1.0.0rc1"
    assert GATE["baseline_release"] == SCENARIOS["baseline_release"] == "1.0.0b3"


def test_package_remains_on_last_qualified_beta_during_rc_work() -> None:
    assert pycrmkit.__version__ == GATE["baseline_release"] == "1.0.0b3"
    assert pycrmkit.__version__ != GATE["target_release"]


def test_prerequisite_v1_milestones_are_explicit_and_backed_by_workflows() -> None:
    prerequisites = GATE["prerequisite_milestones"]

    assert {item["version"] for item in prerequisites} == EXPECTED_PREREQUISITES
    missing = sorted(
        item["workflow"]
        for item in prerequisites
        if not (ROOT / item["workflow"]).is_file()
    )
    assert missing == []


def test_existing_release_qualification_workflows_are_frozen() -> None:
    workflows = GATE["existing_qualification_workflows"]

    assert len(workflows) == 18
    assert len(workflows) == len(set(workflows))
    missing = sorted(path for path in workflows if not (ROOT / path).is_file())
    assert missing == []


def test_rc01_to_rc05_are_implemented_without_claiming_full_rc_qualification() -> None:
    gates = {item["id"]: item for item in GATE["rc_gates"]}

    assert set(gates) == EXPECTED_RC_GATES
    assert all(gates[gate]["status"] == "implemented" for gate in IMPLEMENTED_RC_GATES)
    assert all(
        gates[gate]["status"] == "pending"
        for gate in EXPECTED_RC_GATES - IMPLEMENTED_RC_GATES
    )
    assert GATE["status"] == "qualification-in-progress"
    assert GATE["promotion_ready"] is False


def test_all_implemented_rc_gate_evidence_is_present() -> None:
    implemented = [
        item
        for item in GATE["rc_gates"]
        if item["status"] == "implemented"
    ]

    assert {item["id"] for item in implemented} == IMPLEMENTED_RC_GATES
    missing = sorted(
        path
        for item in implemented
        for path in item["evidence"]
        if not (ROOT / path).is_file()
    )
    assert missing == []


def test_promotion_rule_requires_all_gates_and_zero_blockers() -> None:
    rule = GATE["promotion_rule"]

    assert rule["required_gate_status"] == "qualified"
    assert rule["blocking_failures_allowed"] == 0
    assert rule["candidate_version_after_success"] == "1.0.0rc1"
    assert rule["next_candidate_on_blocking_fix"] == "1.0.0rc2"
