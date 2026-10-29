"""Negative and positive tests for the RC distribution inspector."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.rc1_distribution_manifest import (
    ALEMBIC,
    DJANGO,
    EXTRAS,
    PACKAGE_REQUIRED,
    _metadata,
    _sha256,
)


def _valid_metadata(*, version: str = "1.2.0b3", drop_extra: str | None = None) -> bytes:
    values = sorted(EXTRAS - ({drop_extra} if drop_extra else set()))
    rows = [
        "Metadata-Version: 2.4",
        "Name: pycrmkit",
        f"Version: {version}",
        "Requires-Python: >=3.11,<3.14",
        *(f"Provides-Extra: {item}" for item in values),
        "",
    ]
    return "\n".join(rows).encode("utf-8")


def test_metadata_accepts_complete_supported_dependency_contract() -> None:
    _metadata(_valid_metadata(), "1.2.0b3")


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (_valid_metadata(version="1.2.0rc1"), "1.2.0b3"),
        (_valid_metadata(drop_extra="postgresql"), "1.2.0b3"),
        (_valid_metadata().replace(b">=3.11,<3.14", b">=3.12,<3.14"), "1.2.0b3"),
    ],
)
def test_distribution_inspector_rejects_version_extra_or_python_drift(
    metadata: bytes, expected: str
) -> None:
    with pytest.raises(AssertionError):
        _metadata(metadata, expected)


def test_required_migrations_are_complete_and_adapter_specific() -> None:
    assert len(ALEMBIC) == 6
    assert ALEMBIC[-1] == "0006_campaign_persistence.py"
    assert len(DJANGO) == 5
    assert DJANGO[-1] == "0005_communication_record_store.py"
    assert "pycrmkit/py.typed" in PACKAGE_REQUIRED
    assert all(
        f"pycrmkit/storage/sqlalchemy/migrations/versions/{name}" in PACKAGE_REQUIRED
        for name in ALEMBIC
    )
    assert all(
        f"pycrmkit/integrations/django/migrations/{name}" in PACKAGE_REQUIRED
        for name in DJANGO
    )


def test_artifact_evidence_uses_real_sha256_bytes(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.whl"
    archive.write_bytes(b"RC1 synthetic bytes")
    assert _sha256(archive) == hashlib.sha256(b"RC1 synthetic bytes").hexdigest()
