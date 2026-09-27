"""Consistency checks for immutable PyCRMKit 1.0.0rc1 release evidence."""

from __future__ import annotations

import json
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "release"
REPORT = json.loads(
    (RELEASE / "qualification-report-v1.0.0rc1.json").read_text(encoding="utf-8")
)
MANIFEST = json.loads(
    (RELEASE / "release-manifest-v1.0.0rc1.json").read_text(encoding="utf-8")
)
CHECKSUM_LINES = (
    RELEASE / "SHA256SUMS-v1.0.0rc1.txt"
).read_text(encoding="utf-8").splitlines()

EXPECTED = {
    "pycrmkit-1.0.0rc1-py3-none-any.whl": "3288db9571d39d83c0819af02d8b91eb991be94be57e1d60ba3bd0c3d1a27c41",
    "pycrmkit-1.0.0rc1.tar.gz": "fb8418c4bc0d92c4e302215ca7841a11367cc70adb3c9d0eb6dca67818f951ff",
}


def _checksums() -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in CHECKSUM_LINES:
        digest, filename = line.split(maxsplit=1)
        parsed[filename.strip()] = digest
    return parsed


def test_release_version_and_promotion_are_frozen() -> None:
    assert pycrmkit.__version__ == MANIFEST["version"] == "1.0.0rc1"
    assert REPORT["release"] == "1.0.0rc1"
    assert REPORT["baseline_release"] == "1.0.0b3"
    assert REPORT["status"] == "qualified"
    assert REPORT["promotion_ready"] is True
    assert REPORT["blocking_failures"] == 0


def test_all_seven_rc_gates_are_qualified() -> None:
    assert [item["id"] for item in REPORT["gates"]] == [
        "RC-01",
        "RC-02",
        "RC-03",
        "RC-04",
        "RC-05",
        "RC-06",
        "RC-07",
    ]
    assert {item["status"] for item in REPORT["gates"]} == {"qualified"}


def test_manifest_and_checksum_file_are_identical() -> None:
    checksums = _checksums()
    assert checksums == EXPECTED

    manifest_artifacts = {
        item["filename"]: item["sha256"] for item in MANIFEST["artifacts"]
    }
    assert manifest_artifacts == EXPECTED
    assert MANIFEST["checksum_algorithm"] == "sha256"
    assert MANIFEST["checksum_status"] == "frozen"
    assert MANIFEST["reproducibility"]["required"] is True


def test_release_lineage_points_to_zero_blocker_rc06_commit() -> None:
    expected_commit = "216fd4161f113036fab4f6eb472a530dee65d9a5"
    assert MANIFEST["qualified_code_commit"] == expected_commit
    assert REPORT["qualified_rc06_commit"] == expected_commit
    assert REPORT["promotion_scope"] == "release-metadata-and-evidence-only"
