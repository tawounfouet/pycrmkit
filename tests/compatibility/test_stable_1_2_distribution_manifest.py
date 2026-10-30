"""Negative and positive tests for the stable 1.2 distribution inspector."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from scripts.stable_1_2_distribution_manifest import (
    ALEMBIC,
    DJANGO,
    EXTRAS,
    PACKAGE_REQUIRED,
    _metadata,
    _sha256,
    inspect,
)


def _valid_metadata(
    *, version: str = "1.2.0", drop_extra: str | None = None, readme: str | None = None
) -> bytes:
    values = sorted(EXTRAS - ({drop_extra} if drop_extra else set()))
    rows = [
        "Metadata-Version: 2.4",
        "Name: pycrmkit",
        f"Version: {version}",
        "Requires-Python: >=3.11,<3.14",
        *(f"Provides-Extra: {item}" for item in values),
        *(["Description-Content-Type: text/markdown"] if readme is not None else []),
        "",
        *([readme] if readme is not None else []),
    ]
    return "\n".join(rows).encode("utf-8")


def test_metadata_accepts_complete_supported_dependency_contract() -> None:
    _metadata(_valid_metadata(), "1.2.0")


@pytest.mark.parametrize(
    ("metadata", "expected"),
    [
        (_valid_metadata(version="1.2.0b3"), "1.2.0"),
        (_valid_metadata(drop_extra="postgresql"), "1.2.0"),
        (_valid_metadata().replace(b">=3.11,<3.14", b">=3.12,<3.14"), "1.2.0"),
    ],
)
def test_distribution_inspector_rejects_version_extra_or_python_drift(
    metadata: bytes, expected: str
) -> None:
    with pytest.raises(AssertionError):
        _metadata(metadata, expected)


def test_wheel_and_sdist_metadata_preserve_exact_pypi_readme() -> None:
    readme = "# PyCRMKit\n\nA headless CRM.\n"
    metadata = _valid_metadata(readme=readme)
    _metadata(metadata, "1.2.0", expected_readme=readme)
    with pytest.raises(AssertionError, match="PyPI long description"):
        _metadata(metadata, "1.2.0", expected_readme="# Different\n")
    with pytest.raises(AssertionError):
        _metadata(_valid_metadata(), "1.2.0", expected_readme=readme)


def test_public_readme_links_render_on_pypi() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", readme)
    assert links
    assert all(link.startswith("https://") for link in links), links
    assert "A version present in source control is not necessarily published" in readme


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
        f"pycrmkit/integrations/django/migrations/{name}" in PACKAGE_REQUIRED for name in DJANGO
    )


def test_artifact_evidence_uses_real_sha256_bytes(tmp_path: Path) -> None:
    archive = tmp_path / "synthetic.whl"
    archive.write_bytes(b"Stable synthetic bytes")
    assert _sha256(archive) == hashlib.sha256(b"Stable synthetic bytes").hexdigest()


def test_rc_artifacts_cannot_be_mislabelled_stable(tmp_path: Path) -> None:
    with pytest.raises(AssertionError, match="stable 1.2.0"):
        inspect(tmp_path, "1.2.0rc1")
