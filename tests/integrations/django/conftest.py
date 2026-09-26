"""Minimal Django test environment for the optional adapter."""

from __future__ import annotations

from collections.abc import Iterator

import django
import pytest
from django.conf import settings
from django.core.management import call_command

if not settings.configured:
    settings.configure(
        SECRET_KEY="pycrmkit-django-tests",
        INSTALLED_APPS=[
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "pycrmkit.integrations.django.apps.PyCRMKitDjangoConfig",
        ],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            }
        },
        USE_TZ=True,
        TIME_ZONE="UTC",
        DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
    )

django.setup()

from pycrmkit.integrations.django.models import (  # noqa: E402
    ContactModel,
    OrganizationModel,
    RelationshipModel,
)


@pytest.fixture(scope="session", autouse=True)
def django_schema() -> Iterator[None]:
    """Create the adapter schema through its packaged Django migrations."""

    call_command(
        "migrate",
        "pycrmkit_crm",
        verbosity=0,
        interactive=False,
    )
    yield
    call_command(
        "migrate",
        "pycrmkit_crm",
        "zero",
        verbosity=0,
        interactive=False,
    )


@pytest.fixture(autouse=True)
def clean_django_rows(django_schema: None) -> None:
    """Keep reusable contract and transaction cases isolated."""

    RelationshipModel.objects.all().delete()
    ContactModel.objects.all().delete()
    OrganizationModel.objects.all().delete()
