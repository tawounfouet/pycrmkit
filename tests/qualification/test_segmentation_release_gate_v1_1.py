"""Governance contract for PV1-LOT-007 / PyCRMKit 1.1.0rc1."""

from __future__ import annotations

import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("segmentation_release_gate_v1_1.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_segmentation_rc_targets_the_expected_release() -> None:
    assert MANIFEST["lot"] == "PV1-LOT-007"
    assert MANIFEST["target_release"] == "1.1.0rc1"
    assert MANIFEST["baseline_release"] == "1.1.0b3"
    assert pycrmkit.__version__ in {
        MANIFEST["target_release"],
        MANIFEST["promoted_release"],
    }
    assert MANIFEST["status"] == "qualified"
    assert MANIFEST["promotion_ready"] is True


def test_every_segmentation_rc_gate_has_repository_evidence() -> None:
    assert [gate["id"] for gate in MANIFEST["required_gates"]] == [
        "SEG-RC-01",
        "SEG-RC-02",
        "SEG-RC-03",
        "SEG-RC-04",
        "SEG-RC-05",
        "SEG-RC-06",
        "SEG-RC-07",
    ]
    for gate in MANIFEST["required_gates"]:
        assert gate["evidence"], gate["id"]
        for relative in gate["evidence"]:
            assert (ROOT / relative).exists(), f"{gate['id']}: missing {relative}"


def test_stable_promotion_requires_zero_blockers_and_no_new_scope() -> None:
    rule = MANIFEST["promotion_rule"]
    assert rule["blocking_failures_allowed"] == 0
    assert rule["stable_target_after_success"] == "1.1.0"
    assert rule["next_candidate_on_blocking_fix"] == "1.1.0rc2"
    assert rule["new_feature_scope_allowed"] is False
