"""Executable contract for the published V1 compatibility matrix."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

import pycrmkit

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads(
    (Path(__file__).with_name("compatibility_matrix_v1.json")).read_text(
        encoding="utf-8"
    )
)
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _optional(extra: str) -> list[str]:
    return list(PYPROJECT["project"]["optional-dependencies"][extra])


def test_release_version_matches_compatibility_manifest() -> None:
    assert pycrmkit.__version__ == MANIFEST["version"] == "1.0.0b3"


def test_runtime_python_is_one_of_the_qualified_minor_versions() -> None:
    current = f"{sys.version_info.major}.{sys.version_info.minor}"
    assert current in MANIFEST["python"]


def test_python_install_metadata_matches_qualified_matrix() -> None:
    assert PYPROJECT["project"]["requires-python"] == ">=3.11,<3.14"


def test_persistence_dependency_specs_match_qualified_matrix() -> None:
    sqlalchemy = MANIFEST["dependencies"]["sqlalchemy"]["specifier"]
    psycopg = MANIFEST["dependencies"]["psycopg"]["specifier"]

    assert _optional("sqlalchemy") == [f"SQLAlchemy{sqlalchemy}"]
    assert _optional("postgresql") == [
        f"SQLAlchemy{sqlalchemy}",
        f"psycopg[binary]{psycopg}",
    ]
    assert f"SQLAlchemy{sqlalchemy}" in _optional("migrations")
    assert f"psycopg[binary]{psycopg}" in _optional("migrations")


def test_transport_dependency_specs_match_qualified_matrix() -> None:
    fastapi = MANIFEST["dependencies"]["fastapi"]["specifier"]
    pydantic = MANIFEST["dependencies"]["pydantic"]["specifier"]
    django = MANIFEST["dependencies"]["django"]["specifier"]
    drf = MANIFEST["dependencies"]["drf"]["specifier"]

    assert _optional("fastapi") == [
        f"fastapi{fastapi}",
        f"pydantic{pydantic}",
    ]
    assert _optional("django") == [f"Django{django}"]
    assert _optional("drf") == [
        f"Django{django}",
        f"djangorestframework{drf}",
    ]


def test_provider_dependency_specs_match_qualified_matrix() -> None:
    jinja2 = MANIFEST["dependencies"]["jinja2"]["specifier"]
    resend = MANIFEST["dependencies"]["resend"]["specifier"]

    assert _optional("email") == [f"Jinja2{jinja2}"]
    assert _optional("resend") == [f"resend{resend}"]


def test_required_optional_dependency_combinations_are_published() -> None:
    combinations = {
        item["name"]: tuple(item["extras"])
        for item in MANIFEST["extra_combinations"]
    }

    assert combinations == {
        "core": (),
        "sqlalchemy": ("sqlalchemy",),
        "postgresql": ("postgresql",),
        "migrations": ("migrations",),
        "fastapi": ("fastapi",),
        "django": ("django",),
        "drf": ("drf",),
        "email": ("email",),
        "resend": ("resend",),
        "fastapi-postgresql-migrations": (
            "fastapi",
            "postgresql",
            "migrations",
        ),
        "django-drf-postgresql": (
            "django",
            "drf",
            "postgresql",
        ),
    }
