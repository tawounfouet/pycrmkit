"""Executable V1 stable-promotion gate."""

from __future__ import annotations

import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
QUALIFICATION = ROOT / "tests" / "qualification"

STABLE_GATE = json.loads(
    (QUALIFICATION / "stable_release_gate_v1.json").read_text(encoding="utf-8")
)
RC_REPORT = json.loads(
    (RELEASE / "qualification-report-v1.0.0rc1.json").read_text(encoding="utf-8")
)
RC_MANIFEST = json.loads(
    (RELEASE / "release-manifest-v1.0.0rc1.json").read_text(encoding="utf-8")
)


def assert_stable_release_gate() -> dict[str, object]:
    if pycrmkit.__version__ != STABLE_GATE["target_release"] != "1.0.0":
        raise SystemExit("Stable gate must execute the 1.0.0 package version")

    if STABLE_GATE["source_candidate"] != "1.0.0rc1":
        raise SystemExit("Stable promotion must originate from 1.0.0rc1")
    if STABLE_GATE["source_candidate_commit"] != (
        "1d49db7ec74110bea36d858c4f40c2a59bd34e27"
    ):
        raise SystemExit("Stable source candidate commit drifted")

    if RC_REPORT["release"] != STABLE_GATE["source_candidate"]:
        raise SystemExit("RC report version does not match stable source candidate")
    if RC_REPORT["status"] != "qualified":
        raise SystemExit("Source candidate is not qualified")
    if RC_REPORT["promotion_ready"] is not True:
        raise SystemExit("Source candidate is not promotion-ready")
    if RC_REPORT["blocking_failures"] != 0:
        raise SystemExit("Source candidate has blocking failures")
    if RC_REPORT["artifact_evidence"]["byte_reproducible"] is not True:
        raise SystemExit("Source candidate artifacts are not reproducible")
    if RC_MANIFEST["checksum_status"] != "frozen":
        raise SystemExit("Source candidate checksums are not frozen")
    if RC_MANIFEST["migration_head"] != STABLE_GATE["migration_head"] != "0003":
        raise SystemExit("Stable promotion changed the migration head")

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
        raise SystemExit("Stable promotion policy allows a forbidden functional delta")
    if policy["stable_artifacts_must_be_reproducible"] is not True:
        raise SystemExit("Stable artifacts must be reproducible")

    missing = sorted(
        path
        for path in STABLE_GATE["required_candidate_evidence"]
        if not (ROOT / path).is_file()
    )
    if missing:
        raise SystemExit(f"Missing RC evidence: {missing}")

    return {
        "source_candidate": STABLE_GATE["source_candidate"],
        "target_release": STABLE_GATE["target_release"],
        "package_version": pycrmkit.__version__,
        "functional_delta": STABLE_GATE["functional_delta"],
        "blocking_failures_allowed": STABLE_GATE["blocking_failures_allowed"],
        "migration_head": STABLE_GATE["migration_head"],
        "candidate_qualified": True,
        "stable_evidence_status": STABLE_GATE["status"],
    }


def main() -> None:
    print(json.dumps(assert_stable_release_gate(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
