"""Build audited 1.2.0rc1 exact-main archives and checksums, without publication."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import tarfile
import zipfile
from datetime import UTC, datetime
from email.parser import Parser
from pathlib import Path
from typing import Any

VERSION = "1.2.0rc1"
TAG = "v1.2.0rc1"
_SHA = re.compile(r"[0-9a-f]{40}\Z")


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def _metadata(source: bytes) -> None:
    data = Parser().parsestr(source.decode("utf-8"))
    if data["Name"].casefold() != "pycrmkit" or data["Version"] != VERSION:
        raise ValueError("Distribution version/name mismatch")


def verify_checksums(dist: Path, checksums: Path) -> None:
    for line in checksums.read_text(encoding="utf-8").splitlines():
        columns = line.split("  ", 1)
        if len(columns) != 2 or re.fullmatch(r"[0-9a-f]{64}", columns[0]) is None:
            raise ValueError("Malformed SHA256SUMS entry")
        sha, name = columns
        if Path(name).name != name:
            raise ValueError("Unsafe archive path")
        file = dist / name
        if not file.is_file() or digest(file) != sha:
            raise ValueError("Artifact SHA256 mismatch")


def prepare_bundle(*, dist: Path, source_sha: str, build_run_id: int) -> dict[str, Any]:
    """Fail closed; this function NEVER creates a tag or release."""
    if _SHA.fullmatch(source_sha) is None:
        raise ValueError("Expected exact lowercase 40-character source SHA")
    if build_run_id < 1:
        raise ValueError("Expected positive build run ID")
    wheel = dist / f"pycrmkit-{VERSION}-py3-none-any.whl"
    sdist = dist / f"pycrmkit-{VERSION}.tar.gz"
    if not wheel.is_file() or not sdist.is_file():
        raise ValueError("Both exact RC distributions are required")
    with zipfile.ZipFile(wheel) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt wheel")
        _metadata(archive.read(f"pycrmkit-{VERSION}.dist-info/METADATA"))
        for resource in (
            "pycrmkit/py.typed",
            "pycrmkit/storage/sqlalchemy/migrations/versions/0006_campaign_persistence.py",
            "pycrmkit/integrations/django/migrations/0005_communication_record_store.py",
        ):
            if resource not in archive.namelist():
                raise ValueError(f"Missing wheel resource: {resource}")
    with tarfile.open(sdist, "r:gz") as archive:
        info = archive.extractfile(f"pycrmkit-{VERSION}/PKG-INFO")
        if info is None:
            raise ValueError("Missing sdist metadata")
        _metadata(info.read())
        if f"pycrmkit-{VERSION}/src/pycrmkit/py.typed" not in archive.getnames():
            raise ValueError("Missing sdist typing marker")
    files = [
        {"name": file.name, "bytes": file.stat().st_size, "sha256": digest(file)}
        for file in (wheel, sdist)
    ]
    checksums = dist / f"SHA256SUMS-{TAG}.txt"
    manifest = dist / f"release-manifest-{TAG}.json"
    if checksums.exists() or manifest.exists():
        raise ValueError("Refuse to overwrite existing release evidence")
    report: dict[str, Any] = {
        "schema": "pycrmkit.rc1.release_evidence.v1",
        "project": "pycrmkit",
        "version": VERSION,
        "tag_intent": TAG,
        "source_sha": source_sha,
        "build_run_id": build_run_id,
        "built_utc": datetime.now(UTC).isoformat(),
        "publication_authorized": False,
        "publication_state": "EVIDENCE_ONLY_NOT_RELEASED",
        "pypi_state": "NOT_VERIFIED_NOT_PUBLISHED_BY_THIS_WORKFLOW",
        "artifacts": files,
    }
    checksums.write_text(
        "".join(f"{item['sha256']}  {item['name']}\n" for item in files),
        encoding="utf-8",
    )
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify_checksums(dist, checksums)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--build-run-id", type=int, required=True)
    args = parser.parse_args()
    evidence = prepare_bundle(
        dist=args.dist, source_sha=args.source_sha, build_run_id=args.build_run_id,
    )
    print(f"RC1 evidence verified for {evidence['source_sha']} (NO PUBLISH)")


if __name__ == "__main__":
    main()
