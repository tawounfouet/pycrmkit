"""Django application bridge foundation tests."""

from __future__ import annotations

import subprocess
import sys

from django.apps import apps

from pycrmkit.integrations.django.apps import PyCRMKitDjangoConfig
from pycrmkit.integrations.django.models import (
    ContactModel,
    OrganizationModel,
    RelationshipModel,
)


def test_app_config_is_loaded_under_a_non_generic_label() -> None:
    config = apps.get_app_config("pycrmkit_crm")
    assert isinstance(config, PyCRMKitDjangoConfig)
    assert config.name == "pycrmkit.integrations.django"


def test_django_models_are_distinct_persistence_types() -> None:
    assert ContactModel._meta.db_table == "pycrmkit_contacts"
    assert OrganizationModel._meta.db_table == "pycrmkit_organizations"
    assert RelationshipModel._meta.db_table == "pycrmkit_relationships"


def test_core_import_does_not_require_django() -> None:
    script = r"""
import builtins

real_import = builtins.__import__


def guarded(name, *args, **kwargs):
    if name == "django" or name.startswith("django."):
        raise AssertionError("core import attempted to import Django")
    return real_import(name, *args, **kwargs)


builtins.__import__ = guarded
import pycrmkit
assert pycrmkit.__version__
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
