"""Executable PyCRMKit 1.1 stable-promotion gate."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
QUALIFICATION = ROOT / "tests" / "qualification"

STABLE_GATE = json.loads(
    (QUALIFICATION / "stable_release_gate_v1_1.json").read_text(encoding="utf-8")
)
RC_QUALIFICATION = json.loads(
    (QUALIFICATION / "segmentation_release_gate_v1_1.json").read_text(
        encoding="utf-8"
    )
)
RC_REPORT = json.loads(
    (RELEASE / "qualification-report-v1.1.0rc1.json").read_text(encoding="utf-8")
)
RC_MANIFEST = json.loads(
    (RELEASE / "release-manifest-v1.1.0rc1.json").read_text(encoding="utf-8")
)
STABLE_REPORT = json.loads(
    (RELEASE / "qualification-report-v1.1.0.json").read_text(encoding="utf-8")
)
STABLE_MANIFEST = json.loads(
    (RELEASE / "release-manifest-v1.1.0.json").read_text(encoding="utf-8")
)


def assert_stable_release_gate(*, require_runtime_version: bool = True) -> dict[str, object]:
    if require_runtime_version and pycrmkit.__version__ != "1.1.0":
        raise SystemExit("Stable gate must execute against PyCRMKit 1.1.0")

    if STABLE_GATE["source_candidate"] != "1.1.0rc1":
        raise SystemExit("Stable promotion must originate from 1.1.0rc1")
    if STABLE_GATE["source_candidate_commit"] != (
        "d703f264a60304d505159f2fd42fc50bdf78e927"
    ):
        raise SystemExit("Stable source candidate commit drifted")
    if STABLE_GATE["target_release"] != "1.1.0":
        raise SystemExit("Stable target must remain 1.1.0")

    if RC_QUALIFICATION["status"] != "qualified":
        raise SystemExit("Segmentation RC qualification is not qualified")
    if RC_QUALIFICATION["promotion_ready"] is not True:
        raise SystemExit("Segmentation RC is not promotion-ready")
    if RC_REPORT["status"] != "qualified":
        raise SystemExit("RC release report is not qualified")
    if RC_REPORT["promotion_ready"] is not True:
        raise SystemExit("RC release report is not promotion-ready")
    if RC_REPORT["blocking_failures"] != 0:
        raise SystemExit("RC has blocking failures")
    if RC_REPORT["artifact_evidence"]["byte_reproducible"] is not True:
        raise SystemExit("RC artifacts are not reproducible")
    if RC_MANIFEST["checksum_status"] != "frozen":
        raise SystemExit("RC checksums are not frozen")

    if STABLE_REPORT["functional_delta_from_rc1"] != "none":
        raise SystemExit("Stable report declares a functional delta")
    if STABLE_REPORT["artifact_evidence"]["byte_reproducible"] is not True:
        raise SystemExit("Stable artifacts are not reproducible")
    stable_checksum_status = STABLE_MANIFEST["checksum_status"]
    require_final_checksum_freeze = (
        os.environ.get("PYCRMKIT_REQUIRE_FINAL_CHECKSUM_FREEZE") == "1"
    )
    if stable_checksum_status not in {"pending-final-freeze", "frozen"}:
        raise SystemExit("Stable checksum status is invalid")
    if require_final_checksum_freeze and stable_checksum_status != "frozen":
        raise SystemExit("Stable checksums are not frozen")

    expected_sqlalchemy = STABLE_GATE["sqlalchemy_migration_head"]
    expected_django = STABLE_GATE["django_migration_head"]
    if expected_sqlalchemy != "0005":
        raise SystemExit("Stable SQLAlchemy migration head drifted")
    if expected_django != "0003_segmentation":
        raise SystemExit("Stable Django migration head drifted")
    for evidence in (RC_REPORT, RC_MANIFEST, STABLE_REPORT, STABLE_MANIFEST):
        if evidence["sqlalchemy_migration_head"] != expected_sqlalchemy:
            raise SystemExit("SQLAlchemy migration evidence drifted")
        if evidence["django_migration_head"] != expected_django:
            raise SystemExit("Django migration evidence drifted")

    if STABLE_GATE["functional_delta"] != "none":
        raise SystemExit("Stable promotion must have no functional delta")
    if STABLE_GATE["blocking_failures_allowed"] != 0:
        raise SystemExit("Stable promotion allows no blockers")

    policy = STABLE_GATE["policy"]
    prohibited = (
        "new_features_allowed",
        "new_public_api_allowed",
        "persistence_schema_change_allowed",
        "migration_change_allowed",
    )
    if any(policy[name] is not False for name in prohibited):
        raise SystemExit("Stable policy allows a forbidden functional delta")
    if policy["stable_artifacts_must_be_reproducible"] is not True:
        raise SystemExit("Stable artifacts must be reproducible")

    required = (
        STABLE_GATE["required_candidate_evidence"]
        + STABLE_GATE["required_stable_evidence"]
    )
    missing = sorted(path for path in required if not (ROOT / path).is_file())
    if missing:
        raise SystemExit(f"Missing 1.1 stable evidence: {missing}")

    return {
        "source_candidate": STABLE_GATE["source_candidate"],
        "source_candidate_commit": STABLE_GATE["source_candidate_commit"],
        "target_release": STABLE_GATE["target_release"],
        "package_version": pycrmkit.__version__,
        "functional_delta": STABLE_GATE["functional_delta"],
        "blocking_failures_allowed": STABLE_GATE["blocking_failures_allowed"],
        "sqlalchemy_migration_head": expected_sqlalchemy,
        "django_migration_head": expected_django,
        "candidate_qualified": True,
        "stable_status": STABLE_GATE["status"],
        "promotion_ready": STABLE_GATE["promotion_ready"],
        "stable_checksum_status": stable_checksum_status,
    }


def main() -> None:
    print(json.dumps(assert_stable_release_gate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
