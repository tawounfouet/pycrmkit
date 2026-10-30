"""LOT-32-010: inspect stable 1.2.0 candidate artifacts without publication.

This inspector never imports the source package and never publishes anything.
Candidate SHA-256 values do not stand in for immutable GitHub release assets.
The historical RC1 inspector and its manifest contract remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

ALEMBIC = (
    "0001_persistence_baseline.py",
    "0002_align_repository_reference_semantics.py",
    "0003_external_identities.py",
    "0004_task_type.py",
    "0005_segmentation_persistence.py",
    "0006_campaign_persistence.py",
)
DJANGO = (
    "0001_initial.py",
    "0002_external_identity.py",
    "0003_segmentation.py",
    "0004_campaign_persistence.py",
    "0005_communication_record_store.py",
)
EXTRAS = {
    "sqlalchemy",
    "postgresql",
    "migrations",
    "fastapi",
    "django",
    "drf",
    "email",
    "resend",
    "dev",
}
PACKAGE_REQUIRED = (
    {
        "pycrmkit/py.typed",
        "pycrmkit/__about__.py",
        "pycrmkit/campaigns/__init__.py",
        "pycrmkit/campaigns/data_operations.py",
        "pycrmkit/integrations/django/migrations/__init__.py",
        "pycrmkit/storage/sqlalchemy/migrations/env.py",
        "pycrmkit/storage/sqlalchemy/migrations/README.md",
        "pycrmkit/storage/sqlalchemy/migrations/script.py.mako",
        "pycrmkit/storage/sqlalchemy/migrations/cli.py",
    }
    | {f"pycrmkit/storage/sqlalchemy/migrations/versions/{revision}" for revision in ALEMBIC}
    | {f"pycrmkit/integrations/django/migrations/{revision}" for revision in DJANGO}
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _metadata(raw: bytes, version: str) -> None:
    parsed = Parser().parsestr(raw.decode("utf-8"))
    assert parsed["Name"].casefold() == "pycrmkit"
    assert parsed["Version"] == version, (parsed["Version"], version)
    assert {part.strip() for part in parsed["Requires-Python"].split(",")} == {">=3.11", "<3.14"}, (
        parsed["Requires-Python"]
    )
    extras = set(parsed.get_all("Provides-Extra", []))
    assert extras == EXTRAS, (sorted(extras), sorted(EXTRAS))
    assert not any(
        word in str(parsed).casefold()
        for word in (
            "dependency_links",
            "localhost:5432",
            "test_password",
        )
    )


def inspect(dist: Path, version: str) -> dict[str, object]:
    assert version == "1.2.0", "stable 1.2.0 artifacts required"
    # The wheel is pure Python, while the sdist must preserve all migration
    # sources and public package resources; neither can silently lose files.
    wheel_name = f"pycrmkit-{version}-py3-none-any.whl"
    sdist_name = f"pycrmkit-{version}.tar.gz"
    expected = {wheel_name, sdist_name}
    assert {p.name for p in dist.iterdir() if p.is_file()} == expected
    wheel = dist / wheel_name
    sdist = dist / sdist_name
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        missing = PACKAGE_REQUIRED - names
        assert not missing, ("wheel missing", sorted(missing))
        assert not any(
            name.startswith(("tests/", "examples/", ".github/", "scripts/", "benchmarks/"))
            for name in names
        )
        metadata_path = f"pycrmkit-{version}.dist-info/METADATA"
        entry_path = f"pycrmkit-{version}.dist-info/entry_points.txt"
        record_path = f"pycrmkit-{version}.dist-info/RECORD"
        assert {metadata_path, entry_path, record_path} <= names
        _metadata(archive.read(metadata_path), version)
        assert "pycrmkit-migrate" in archive.read(entry_path).decode()
    prefix = f"pycrmkit-{version}/"
    with tarfile.open(sdist, "r:gz") as archive:
        names = set(archive.getnames())
        members = {name for name in names if name.startswith(prefix)}
        assert members, "sdist has no versioned root"
        must = {
            prefix + "pyproject.toml",
            prefix + "README.md",
            prefix + "LICENSE",
            prefix + "src/pycrmkit/__about__.py",
            prefix + "src/pycrmkit/py.typed",
            prefix + "PKG-INFO",
        } | {prefix + "src/" + x for x in PACKAGE_REQUIRED}
        assert must <= members, ("sdist missing", sorted(must - members))
        info = archive.extractfile(prefix + "PKG-INFO")
        assert info is not None
        _metadata(info.read(), version)
        assert not any(name.startswith("/") or ".." in Path(name).parts for name in names), (
            "Unsafe source archive path"
        )

    # All hashes are output for verification of the current CI artifact.
    # They are NOT publication checksums until stable GO and immutable asset verification.
    return {
        "schema": "pycrmkit.stable.distribution_qualification.v1",
        "candidate_label": "LOT-32-010 source-exact stable candidate; NOT PUBLISHED",
        "built_package_version": version,
        "target_stable_version": "1.2.0",
        "publication_authorized": False,
        "requires_python": ">=3.11,<3.14",
        "expected_extras": sorted(EXTRAS),
        "packaged_alembic_revisions": list(ALEMBIC),
        "packaged_django_migrations": list(DJANGO),
        "files": [
            {"name": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)}
            for p in (wheel, sdist)
        ],
        "wheel_and_sdist_contents_passed": True,
        "passed": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.dist, args.expected_version)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("Distribution contents, metadata and hashes: PASS", args.expected_version)


if __name__ == "__main__":
    main()
