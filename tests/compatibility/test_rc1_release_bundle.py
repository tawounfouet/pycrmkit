"""Guarded RC1 evidence generation: artifacts may not be published from this module."""
from __future__ import annotations

import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.rc1_release_bundle import VERSION, prepare_bundle, verify_checksums


def _artifacts(dist: Path) -> None:
    with zipfile.ZipFile(dist / f"pycrmkit-{VERSION}-py3-none-any.whl", "w") as wheel:
        wheel.writestr(
            f"pycrmkit-{VERSION}.dist-info/METADATA",
            f"Metadata-Version: 2.4\nName: pycrmkit\nVersion: {VERSION}\n",
        )
        for name in (
            "pycrmkit/py.typed",
            "pycrmkit/storage/sqlalchemy/migrations/versions/0006_campaign_persistence.py",
            "pycrmkit/integrations/django/migrations/0005_communication_record_store.py",
        ):
            wheel.writestr(name, "")
    with tarfile.open(dist / f"pycrmkit-{VERSION}.tar.gz", "w:gz") as sdist:
        for name, contents in (
            (f"pycrmkit-{VERSION}/PKG-INFO",
             f"Metadata-Version: 2.4\nName: pycrmkit\nVersion: {VERSION}\n".encode()),
            (f"pycrmkit-{VERSION}/src/pycrmkit/py.typed", b""),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(contents)
            sdist.addfile(info, io.BytesIO(contents))


def test_bundle_emits_no_publication_and_detects_tampering(tmp_path: Path) -> None:
    _artifacts(tmp_path)
    report = prepare_bundle(dist=tmp_path, source_sha="a" * 40, build_run_id=123)
    assert report["publication_authorized"] is False
    assert report["publication_state"] == "EVIDENCE_ONLY_NOT_RELEASED"
    assert report["source_sha"] == "a" * 40
    assert len(report["artifacts"]) == 2
    assert json.loads((tmp_path / "release-manifest-v1.2.0rc1.json").read_text()) == report
    checksums = tmp_path / "SHA256SUMS-v1.2.0rc1.txt"
    verify_checksums(tmp_path, checksums)
    with pytest.raises(ValueError, match="overwrite"):
        prepare_bundle(dist=tmp_path, source_sha="a" * 40, build_run_id=123)
    (tmp_path / report["artifacts"][0]["name"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="mismatch"):
        verify_checksums(tmp_path, checksums)


def test_bad_source_and_build_run_are_no_go(tmp_path: Path) -> None:
    _artifacts(tmp_path)
    with pytest.raises(ValueError, match="40-character"):
        prepare_bundle(dist=tmp_path, source_sha="bad-sha", build_run_id=123)
    with pytest.raises(ValueError, match="positive"):
        prepare_bundle(dist=tmp_path, source_sha="a" * 40, build_run_id=0)


def test_missing_sdist_is_no_go(tmp_path: Path) -> None:
    _artifacts(tmp_path)
    (tmp_path / f"pycrmkit-{VERSION}.tar.gz").unlink()
    with pytest.raises(ValueError, match="Both exact"):
        prepare_bundle(dist=tmp_path, source_sha="a" * 40, build_run_id=123)
    assert not (tmp_path / "release-manifest-v1.2.0rc1.json").exists()
