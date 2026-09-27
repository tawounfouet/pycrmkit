"""RC-04 integration invariants for the PyCRMKit V1 candidate."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FASTAPI_ROUTER_ROOT = ROOT / "src/pycrmkit/integrations/fastapi"
DRF_VIEWS = ROOT / "src/pycrmkit/integrations/django/drf/views.py"
DJANGO_REPOSITORIES = ROOT / "src/pycrmkit/integrations/django/repositories.py"

FORBIDDEN_FASTAPI_IMPORT_PREFIXES = (
    "sqlalchemy",
    "pycrmkit.storage.sqlalchemy",
)
FORBIDDEN_DRF_IMPORT_PREFIXES = (
    "django.db",
    "pycrmkit.integrations.django.models",
    "pycrmkit.integrations.django.repositories",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def _violations(paths: list[Path], forbidden: tuple[str, ...]) -> list[str]:
    violations: list[str] = []
    for path in paths:
        for imported in sorted(_imports(path)):
            if any(
                imported == prefix or imported.startswith(f"{prefix}.")
                for prefix in forbidden
            ):
                violations.append(f"{path.relative_to(ROOT)} -> {imported}")
    return violations


def test_fastapi_http_surface_does_not_bypass_facade_into_sqlalchemy() -> None:
    paths = [
        FASTAPI_ROUTER_ROOT / "dependencies.py",
        FASTAPI_ROUTER_ROOT / "router.py",
        *sorted((FASTAPI_ROUTER_ROOT / "routers").glob("*.py")),
    ]

    assert _violations(paths, FORBIDDEN_FASTAPI_IMPORT_PREFIXES) == []


def test_drf_viewsets_do_not_bypass_facade_into_django_orm() -> None:
    assert _violations([DRF_VIEWS], FORBIDDEN_DRF_IMPORT_PREFIXES) == []

    source = DRF_VIEWS.read_text(encoding="utf-8")
    assert "from pycrmkit import CRM" in source
    assert "get_crm(" in source


def test_django_persistence_scope_is_explicit_not_full_unit_of_work() -> None:
    source = DJANGO_REPOSITORIES.read_text(encoding="utf-8")

    assert "class DjangoContactRepository" in source
    assert "class DjangoOrganizationRepository" in source
    assert "class DjangoRelationshipRepository" in source
    assert "class DjangoExternalIdentityRepository" in source

    # RC-04 must not silently claim cross-domain Django parity with SQLAlchemy.
    assert "class DjangoActivityRepository" not in source
    assert "class DjangoTaskRepository" not in source
    assert "class DjangoLeadRepository" not in source
    assert "class DjangoOpportunityRepository" not in source


def test_integration_release_evidence_exists_for_source_and_wheel_paths() -> None:
    required = {
        ".github/workflows/fastapi-e2e.yml",
        ".github/workflows/django-e2e.yml",
        ".github/workflows/django.yml",
        ".github/workflows/drf.yml",
        "tests/integrations/fastapi/test_postgresql_e2e.py",
        "tests/integrations/drf/test_views.py",
        "tests/integrations/django/test_external_identities_repository.py",
    }

    missing = sorted(path for path in required if not (ROOT / path).is_file())
    assert missing == []
